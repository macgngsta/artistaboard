#!/usr/bin/env bash
#
# provision-wsl.sh
# ----------------
# Linux-side provisioning for the single-node k3s dev server. It is invoked by
# Install-K3sCluster.ps1 inside WSL2 Ubuntu, as root, and is idempotent: every
# step checks current state before acting so re-runs are safe.
#
# Responsibilities:
#   * ensure a non-root login user owns ~/cluster and the kubeconfig
#   * update apt and install the required base packages
#   * install k3s from the official Rancher installer (get.k3s.io)
#   * wait for and verify cluster health (node, CoreDNS, Traefik, local-path)
#   * make kubectl usable for both root and the login user
#   * scaffold ~/cluster/{apps,manifests,postgres,redis} with example manifests
#
# Environment:
#   CLUSTER_USER  Linux username that should own ~/cluster (defaults to the
#                 invoking sudo user, else 'k3s').
#
# Only official sources are used. k3s ships CoreDNS, Traefik ingress, and the
# local-path storage provisioner in-box, so no third-party add-ons are needed.

set -euo pipefail

# ---------------------------------------------------------------------------
# Logging helpers - everything goes to stdout (captured by the PowerShell log).
# ---------------------------------------------------------------------------
log()  { printf '[provision] %s\n' "$*"; }
step() { printf '\n[provision] === %s ===\n' "$*"; }
die()  { printf '[provision] ERROR: %s\n' "$*" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] || die 'This script must run as root inside WSL.'

# ---------------------------------------------------------------------------
# Resolve the login user that will own the cluster workspace + kubeconfig.
# ---------------------------------------------------------------------------
CLUSTER_USER="${CLUSTER_USER:-${SUDO_USER:-k3s}}"

ensure_user() {
    step "Ensuring login user '$CLUSTER_USER'"
    if id "$CLUSTER_USER" >/dev/null 2>&1; then
        log "User '$CLUSTER_USER' already exists."
    else
        log "Creating user '$CLUSTER_USER'."
        adduser --disabled-password --gecos '' "$CLUSTER_USER"
    fi
    # Passwordless sudo keeps automated re-runs non-interactive on this dev box.
    usermod -aG sudo "$CLUSTER_USER"
    echo "$CLUSTER_USER ALL=(ALL) NOPASSWD:ALL" > "/etc/sudoers.d/90-$CLUSTER_USER"
    chmod 0440 "/etc/sudoers.d/90-$CLUSTER_USER"

    # Make this user the distro default so `wsl -d Ubuntu` lands as them.
    if [ ! -f /etc/wsl.conf ] || ! grep -q "default=$CLUSTER_USER" /etc/wsl.conf 2>/dev/null; then
        cat > /etc/wsl.conf <<EOF
# Managed by provision-wsl.sh
[boot]
systemd=true

[user]
default=$CLUSTER_USER
EOF
        log 'Wrote /etc/wsl.conf (systemd enabled, default user set).'
    fi
}

USER_HOME="$(getent passwd "$CLUSTER_USER" | cut -d: -f6)"
[ -n "$USER_HOME" ] || USER_HOME="/home/$CLUSTER_USER"
CLUSTER_DIR="$USER_HOME/cluster"

# ---------------------------------------------------------------------------
# apt packages
# ---------------------------------------------------------------------------
install_packages() {
    step 'Updating apt and installing base packages'
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -y
    apt-get upgrade -y

    local pkgs=(curl git vim unzip jq build-essential ca-certificates)
    local missing=()
    for p in "${pkgs[@]}"; do
        dpkg -s "$p" >/dev/null 2>&1 || missing+=("$p")
    done
    if [ "${#missing[@]}" -gt 0 ]; then
        log "Installing: ${missing[*]}"
        apt-get install -y "${missing[@]}"
    else
        log 'All base packages already installed.'
    fi
}

# ---------------------------------------------------------------------------
# k3s (official Rancher installer)
# ---------------------------------------------------------------------------
install_k3s() {
    step 'Installing k3s (official get.k3s.io installer)'
    if command -v k3s >/dev/null 2>&1 && systemctl is-active --quiet k3s; then
        log 'k3s already installed and running; skipping installer.'
    else
        # --write-kubeconfig-mode 644 lets non-root read the kubeconfig.
        # Traefik + local-path + CoreDNS are bundled and enabled by default.
        curl -sfL https://get.k3s.io | \
            INSTALL_K3S_EXEC="--write-kubeconfig-mode 644" sh -
        log 'k3s installed.'
    fi

    # WSL has no reliable auto-start; make sure the service is up now.
    systemctl enable k3s >/dev/null 2>&1 || true
    systemctl start k3s  || die 'k3s service failed to start (check: journalctl -u k3s).'
}

# ---------------------------------------------------------------------------
# kubectl availability for root and the login user
# ---------------------------------------------------------------------------
configure_kubectl() {
    step 'Configuring kubectl access'
    # k3s bundles kubectl; expose a stable symlink on PATH.
    if [ ! -e /usr/local/bin/kubectl ]; then
        ln -sf /usr/local/bin/k3s /usr/local/bin/kubectl
    fi

    # Give the login user a personal kubeconfig copy so plain `kubectl` works.
    local ukube="$USER_HOME/.kube"
    install -d -o "$CLUSTER_USER" -g "$CLUSTER_USER" "$ukube"
    cp /etc/rancher/k3s/k3s.yaml "$ukube/config"
    chown "$CLUSTER_USER:$CLUSTER_USER" "$ukube/config"
    chmod 600 "$ukube/config"

    # Ensure KUBECONFIG is set in the user's shell for interactive sessions.
    local bashrc="$USER_HOME/.bashrc"
    if ! grep -q 'KUBECONFIG=' "$bashrc" 2>/dev/null; then
        echo 'export KUBECONFIG=$HOME/.kube/config' >> "$bashrc"
        chown "$CLUSTER_USER:$CLUSTER_USER" "$bashrc"
    fi
    log "kubeconfig placed at $ukube/config."
}

# ---------------------------------------------------------------------------
# Health verification: node, CoreDNS, Traefik, local-path
# ---------------------------------------------------------------------------
wait_for() {
    # wait_for <description> <timeout-seconds> <command...>
    local desc="$1" timeout="$2"; shift 2
    local elapsed=0
    until "$@" >/dev/null 2>&1; do
        sleep 5; elapsed=$((elapsed + 5))
        if [ "$elapsed" -ge "$timeout" ]; then
            die "Timed out after ${timeout}s waiting for: $desc"
        fi
        log "waiting for $desc ... (${elapsed}s)"
    done
    log "OK: $desc"
}

verify_cluster() {
    step 'Verifying cluster health'
    export KUBECONFIG=/etc/rancher/k3s/k3s.yaml

    wait_for 'node Ready' 180 \
        bash -c "kubectl get nodes --no-headers | grep -qw Ready"
    wait_for 'CoreDNS available' 180 \
        bash -c "kubectl -n kube-system wait --for=condition=Available deploy/coredns --timeout=10s"
    wait_for 'Traefik available' 240 \
        bash -c "kubectl -n kube-system wait --for=condition=Available deploy/traefik --timeout=10s"
    wait_for 'local-path provisioner available' 180 \
        bash -c "kubectl -n kube-system wait --for=condition=Available deploy/local-path-provisioner --timeout=10s"

    log 'Cluster components healthy:'
    kubectl get nodes
    kubectl -n kube-system get deploy coredns traefik local-path-provisioner
    kubectl get storageclass
}

# ---------------------------------------------------------------------------
# Workspace scaffold + example manifests
# ---------------------------------------------------------------------------
scaffold_workspace() {
    step "Creating workspace at $CLUSTER_DIR"
    install -d -o "$CLUSTER_USER" -g "$CLUSTER_USER" \
        "$CLUSTER_DIR" \
        "$CLUSTER_DIR/apps" \
        "$CLUSTER_DIR/manifests" \
        "$CLUSTER_DIR/postgres" \
        "$CLUSTER_DIR/redis"

    write_manifests
    chown -R "$CLUSTER_USER:$CLUSTER_USER" "$CLUSTER_DIR"
    log "Workspace ready. Apply with: kubectl apply -f $CLUSTER_DIR/manifests/"
}

# write_manifests emits example manifests sized for a 16 GB machine. Requests are
# modest so several workloads coexist; limits cap runaway usage. Total requested
# across the samples stays well under the 6 GB the WSL VM is given.
write_manifests() {
    local M="$CLUSTER_DIR/manifests"

    # --- Namespace ---------------------------------------------------------
    cat > "$M/00-namespace.yaml" <<'YAML'
# Dedicated namespace so the sample app stack is easy to inspect and delete.
apiVersion: v1
kind: Namespace
metadata:
  name: apps
YAML

    # --- Shared secret (demo credentials) ---------------------------------
    cat > "$M/05-secrets.yaml" <<'YAML'
# Demo credentials. Replace these before exposing anything beyond your LAN.
apiVersion: v1
kind: Secret
metadata:
  name: app-credentials
  namespace: apps
type: Opaque
stringData:
  POSTGRES_DB: appdb
  POSTGRES_USER: appuser
  POSTGRES_PASSWORD: change-me-please
  # DSNs consumed by the web app and Huey workers.
  DATABASE_URL: postgresql://appuser:change-me-please@postgres:5432/appdb
  REDIS_URL: redis://redis:6379/0
YAML

    # --- PostgreSQL StatefulSet + headless Service + PVC -------------------
    cat > "$M/10-postgres.yaml" <<'YAML'
# PostgreSQL as a StatefulSet with a PersistentVolumeClaim backed by the k3s
# default local-path storage class (data lives on the NVMe SSD).
apiVersion: v1
kind: Service
metadata:
  name: postgres
  namespace: apps
  labels: { app: postgres }
spec:
  # Headless service gives the pod a stable DNS name: postgres.apps.svc.
  clusterIP: None
  selector: { app: postgres }
  ports:
    - name: postgres
      port: 5432
      targetPort: 5432
---
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: postgres
  namespace: apps
spec:
  serviceName: postgres
  replicas: 1
  selector:
    matchLabels: { app: postgres }
  template:
    metadata:
      labels: { app: postgres }
    spec:
      containers:
        - name: postgres
          image: postgres:16-alpine
          ports:
            - containerPort: 5432
          envFrom:
            - secretRef: { name: app-credentials }
          env:
            # Keep PGDATA in a subdir so the mount root can hold lost+found.
            - name: PGDATA
              value: /var/lib/postgresql/data/pgdata
          resources:
            requests: { cpu: "250m", memory: "512Mi" }
            limits:   { cpu: "1000m", memory: "1Gi" }
          volumeMounts:
            - name: data
              mountPath: /var/lib/postgresql/data
          readinessProbe:
            exec: { command: ["pg_isready", "-U", "appuser", "-d", "appdb"] }
            initialDelaySeconds: 10
            periodSeconds: 10
  volumeClaimTemplates:
    - metadata:
        name: data
      spec:
        accessModes: ["ReadWriteOnce"]
        storageClassName: local-path
        resources:
          requests:
            storage: 8Gi
YAML

    # --- Redis Deployment + Service + PVC ----------------------------------
    cat > "$M/20-redis.yaml" <<'YAML'
# Redis for caching and the Huey task queue broker. A small PVC persists data
# across restarts (appendonly enabled).
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: redis-data
  namespace: apps
spec:
  accessModes: ["ReadWriteOnce"]
  storageClassName: local-path
  resources:
    requests:
      storage: 1Gi
---
apiVersion: v1
kind: Service
metadata:
  name: redis
  namespace: apps
  labels: { app: redis }
spec:
  selector: { app: redis }
  ports:
    - name: redis
      port: 6379
      targetPort: 6379
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: redis
  namespace: apps
spec:
  replicas: 1
  selector:
    matchLabels: { app: redis }
  template:
    metadata:
      labels: { app: redis }
    spec:
      containers:
        - name: redis
          image: redis:7-alpine
          args: ["redis-server", "--appendonly", "yes"]
          ports:
            - containerPort: 6379
          resources:
            requests: { cpu: "100m", memory: "128Mi" }
            limits:   { cpu: "500m", memory: "256Mi" }
          volumeMounts:
            - name: data
              mountPath: /data
          readinessProbe:
            exec: { command: ["redis-cli", "ping"] }
            initialDelaySeconds: 5
            periodSeconds: 10
      volumes:
        - name: data
          persistentVolumeClaim:
            claimName: redis-data
YAML

    # --- Sample web Deployment + Service -----------------------------------
    cat > "$M/30-web.yaml" <<'YAML'
# Sample web application. Replace the image with your own app image; it is wired
# to Postgres and Redis via the shared secret. Traefik/whoami is used as a
# harmless placeholder that returns request info so ingress is easy to test.
apiVersion: v1
kind: Service
metadata:
  name: web
  namespace: apps
  labels: { app: web }
spec:
  selector: { app: web }
  ports:
    - name: http
      port: 80
      targetPort: 80
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: web
  namespace: apps
spec:
  replicas: 2
  selector:
    matchLabels: { app: web }
  template:
    metadata:
      labels: { app: web }
    spec:
      containers:
        - name: web
          image: traefik/whoami:latest   # replace with your app image
          ports:
            - containerPort: 80
          envFrom:
            - secretRef: { name: app-credentials }
          resources:
            requests: { cpu: "100m", memory: "128Mi" }
            limits:   { cpu: "500m", memory: "256Mi" }
          readinessProbe:
            httpGet: { path: /, port: 80 }
            initialDelaySeconds: 5
            periodSeconds: 10
YAML

    # --- Huey worker Deployment --------------------------------------------
    cat > "$M/40-huey-worker.yaml" <<'YAML'
# Huey background workers. Replace the image/command with your own worker entry
# point (e.g. `python -m huey.bin.huey_consumer app.huey`). No Service/ingress:
# workers pull jobs from Redis. Two replicas share the queue.
apiVersion: apps/v1
kind: Deployment
metadata:
  name: huey-worker
  namespace: apps
spec:
  replicas: 2
  selector:
    matchLabels: { app: huey-worker }
  template:
    metadata:
      labels: { app: huey-worker }
    spec:
      containers:
        - name: huey-worker
          image: python:3.12-slim   # replace with your app image
          # Placeholder command; swap for your real consumer invocation.
          command: ["sh", "-c", "echo 'replace with: huey_consumer app.huey'; sleep infinity"]
          envFrom:
            - secretRef: { name: app-credentials }
          resources:
            requests: { cpu: "100m", memory: "128Mi" }
            limits:   { cpu: "500m", memory: "512Mi" }
YAML

    # --- Ingress (Traefik) -------------------------------------------------
    cat > "$M/50-ingress.yaml" <<'YAML'
# Routes http://web.local/ to the web Service through the bundled Traefik
# ingress controller. Add "<LAN-IP> web.local" to the hosts file of any client
# on your network (or a DNS record) to reach it.
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: web
  namespace: apps
  annotations:
    # k3s ships Traefik as the default IngressClass; entryPoint web = port 80.
    traefik.ingress.kubernetes.io/router.entrypoints: web
spec:
  ingressClassName: traefik
  rules:
    - host: web.local
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: web
                port:
                  number: 80
YAML

    # --- Convenience README inside the workspace ---------------------------
    cat > "$CLUSTER_DIR/README.md" <<'MD'
# ~/cluster

Workspace for the single-node k3s dev server.

    apps/       # (yours) app source / charts / kustomize overlays
    manifests/  # example Kubernetes manifests (apply these)
    postgres/   # (yours) db backups, init SQL, notes
    redis/      # (yours) redis config, notes

## Deploy the samples
    kubectl apply -f ~/cluster/manifests/

## Watch it come up
    kubectl -n apps get pods -w

## Tear the samples down
    kubectl delete -f ~/cluster/manifests/

Replace the placeholder images in 30-web.yaml and 40-huey-worker.yaml with your
own application image, and change the credentials in 05-secrets.yaml.
MD

    log 'Example manifests written to '"$M"
}

# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
main() {
    ensure_user
    install_packages
    install_k3s
    configure_kubectl
    verify_cluster
    scaffold_workspace

    step 'Provisioning complete'
    log "Cluster user : $CLUSTER_USER"
    log "Workspace    : $CLUSTER_DIR"
    log 'Run: kubectl get nodes && kubectl get pods -A'
}

main "$@"
