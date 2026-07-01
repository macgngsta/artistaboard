# Deploying your own apps to k3s

k3s runs on **containerd**, not Docker. That one fact drives everything below:
an image you `docker build` locally is **not** automatically visible to the
cluster — you must either import it into containerd or pull it from a registry.

You have three realistic workflows. Pick one.

---

## Option A — Local build + import (no registry) — simplest for a solo box

Build the image in WSL, import it into k3s's containerd, and roll out. The
[`deploy-app.sh`](./deploy-app.sh) helper does all three steps:

```bash
wsl -d Ubuntu
cd ~/cluster/apps/myapp          # your project with a Dockerfile
~/cluster/deploy-app.sh -n apps -k deployment/web -i myapp/web:dev
```

Under the hood it runs:

```bash
docker build -t myapp/web:dev .
docker save myapp/web:dev -o img.tar
sudo k3s ctr images import img.tar        # <-- into the cluster's containerd
kubectl -n apps set image deployment/web web=myapp/web:dev
kubectl -n apps rollout restart deployment/web
```

> **Critical:** the pod's `imagePullPolicy` must be `IfNotPresent` (or `Never`),
> otherwise kubelet tries to pull `myapp/web:dev` from Docker Hub and fails with
> `ErrImagePull`. `deploy-app.sh` patches this for you; in a manifest set it
> explicitly.

**Pros:** zero infra, fully offline. **Cons:** manual; images live only on this node.

---

## Option B — Local registry in the cluster — best for iterating

Run a registry *inside* k3s, push to it, and reference it by its cluster
address. Good when you rebuild often.

```bash
# One-time: a registry Deployment + Service on a NodePort (e.g. 30500)
kubectl create ns registry
kubectl -n registry create deployment registry --image=registry:2
kubectl -n registry expose deployment registry --port=5000 --type=NodePort \
  --overrides='{"spec":{"ports":[{"port":5000,"nodePort":30500}]}}'

# Tell k3s to trust it (insecure, LAN-only):
sudo tee /etc/rancher/k3s/registries.yaml >/dev/null <<'YAML'
mirrors:
  "localhost:30500":
    endpoint:
      - "http://localhost:30500"
YAML
sudo systemctl restart k3s

# Then, each deploy:
docker build -t localhost:30500/myapp/web:dev .
docker push localhost:30500/myapp/web:dev
kubectl -n apps set image deployment/web web=localhost:30500/myapp/web:dev
```

**Pros:** normal `docker push` flow, standard pull policy. **Cons:** one-time setup.

---

## Option C — External registry (GHCR / Docker Hub) — best for real releases

Push to GitHub Container Registry or Docker Hub from CI or your dev machine, and
let k3s pull normally. This is the path if you want CI-driven deploys.

```bash
# Build & push (e.g. from GitHub Actions or locally):
docker build -t ghcr.io/<you>/web:1.0.0 .
docker push ghcr.io/<you>/web:1.0.0

# Private repo? create a pull secret once:
kubectl -n apps create secret docker-registry ghcr \
  --docker-server=ghcr.io --docker-username=<you> --docker-password=<PAT>
# then reference it in the pod spec:  imagePullSecrets: [{ name: ghcr }]

kubectl -n apps set image deployment/web web=ghcr.io/<you>/web:1.0.0
```

**Pros:** reproducible, CI-friendly, survives node rebuilds. **Cons:** needs a
registry account + network on every pull.

---

## Recommended flow for this machine

- **Day-to-day iteration:** Option A (`deploy-app.sh`) or Option B (in-cluster registry).
- **Tagged releases / anything you want to reproduce:** Option C (GHCR), ideally
  from GitHub Actions so a push to `main` builds and you just bump the image tag.

## Ongoing management (any option)

```bash
kubectl -n apps get pods -w                     # watch rollout
kubectl -n apps logs -f deployment/web          # tail logs
kubectl -n apps rollout undo deployment/web     # roll back
kubectl -n apps exec -it deploy/web -- sh       # shell into a pod
kubectl -n apps scale deployment/web --replicas=3
```

Consider committing your `~/cluster/manifests/` to git and applying with
`kubectl apply -f manifests/` (or Kustomize) so the cluster state is
declarative and reviewable — that's the maintainable long-term pattern.
