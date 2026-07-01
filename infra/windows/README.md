# Windows 11 → single-node k3s dev server (WSL2)

Turns a Windows 11 Pro desktop into a lightweight, self-hosted Kubernetes box
running a single-node [k3s](https://k3s.io) cluster inside WSL2 Ubuntu, while
leaving the machine fully usable for normal desktop work (including 4K video).

The cluster can host your own web apps, PostgreSQL, Redis, and Huey workers, all
managed as Docker/Kubernetes images and exposed to your LAN through the bundled
Traefik ingress.

- **Installer:** [`Install-K3sCluster.ps1`](./Install-K3sCluster.ps1) — the single PowerShell entry point.
- **Helper:** [`provision-wsl.sh`](./provision-wsl.sh) — Linux-side provisioning run inside WSL (invoked automatically; you don't run it directly).

---

## Prerequisites

| Requirement | Notes |
|---|---|
| Windows 11 Pro (build ≥ 22000) | Works on Win10 too, but Win11 is the target. |
| Administrator account | The installer must run **elevated**. |
| Internet access | Pulls Ubuntu, k3s, kubectl, and container images from official sources. |
| ~Free disk | k3s + images comfortably fit the 512 GB NVMe. |
| Virtualization enabled in BIOS/UEFI | Usually on by default on the Ryzen 7 7730U. |

**Resource budget** (written to `%USERPROFILE%\.wslconfig`): the WSL2 VM is
capped at **6 GB RAM / 6 vCPUs / 4 GB swap**, leaving ~10 GB and idle cores for
Windows and browser video playback.

Only official channels are used: Windows in-box features, `wsl --install` (Microsoft/Canonical),
`get.k3s.io` (Rancher/SUSE), and winget / `dl.k8s.io` for Windows `kubectl`.

---

## Quick start

Open **PowerShell as Administrator**, then:

```powershell
cd infra\windows
powershell -ExecutionPolicy Bypass -File .\Install-K3sCluster.ps1
```

That's it. If enabling virtualization features requires a reboot, the script
registers a one-shot logon task and prompts you — after you log back in, setup
**resumes automatically** from where it left off.

### Options

```powershell
# Skip publishing ports 80/443 to the LAN (localhost-only):
.\Install-K3sCluster.ps1 -SkipLanExposure

# Use a specific distro name or cluster username:
.\Install-K3sCluster.ps1 -Distro Ubuntu -ClusterUser greg

# Re-run just one stage (all stages are idempotent):
.\Install-K3sCluster.ps1 -Stage Prereqs   # Windows features + .wslconfig
.\Install-K3sCluster.ps1 -Stage Wsl       # install Ubuntu + apply .wslconfig
.\Install-K3sCluster.ps1 -Stage Cluster   # provision k3s + manifests + LAN
```

---

## What the installer does

**Stage 1 — Prereqs**
1. Enables Windows features **WSL** (`Microsoft-Windows-Subsystem-Linux`) and
   **Virtual Machine Platform** (idempotent — skips if already enabled).
2. Writes `%USERPROFILE%\.wslconfig` (`memory=6GB`, `processors=6`, `swap=4GB`,
   `localhostForwarding=true`), backing up any existing file.
3. If Windows needs a reboot, registers the resume task and reboots.

**Stage 2 — WSL**
4. Runs `wsl --update` and sets WSL2 as default.
5. Installs **Ubuntu LTS** via `wsl --install -d Ubuntu --no-launch` (skipped if
   already registered).
6. Restarts WSL (`wsl --shutdown`) so `.wslconfig` takes effect.

**Stage 3 — Cluster** (runs `provision-wsl.sh` inside Ubuntu as root)
7. Creates a login user that owns `~/cluster` and the kubeconfig; enables systemd.
8. `apt update && upgrade`, installs **curl, git, vim, unzip, jq, build-essential**.
9. Installs **k3s** from `get.k3s.io` (bundles CoreDNS, Traefik, local-path).
10. **Verifies health**: node `Ready`, and `coredns`, `traefik`,
    `local-path-provisioner` all `Available`.
11. Configures **kubectl** inside Ubuntu (for root and the login user).
12. Copies the kubeconfig to Windows (`%USERPROFILE%\.kube\config`) and sets the
    user `KUBECONFIG` so **kubectl works from PowerShell too** (via
    `localhostForwarding` to `127.0.0.1:6443`).
13. Installs **kubectl on Windows** (winget → `dl.k8s.io` fallback) if missing.
14. Publishes Traefik ports **80/443** from the NAT'd WSL2 VM to your LAN via
    `netsh portproxy` + firewall rules, and installs a logon task that keeps the
    proxy pointed at the (dynamic) WSL IP across reboots.
15. Scaffolds `~/cluster/{apps,manifests,postgres,redis}` and writes example
    manifests.
16. Prints your LAN IP and verification/next-step commands.

**Logs** are written to `%USERPROFILE%\k3s-setup\install.log`.

---

## How to verify the installation

From **Windows PowerShell** or **inside WSL** (`wsl -d Ubuntu`):

```bash
kubectl get nodes      # node should be Ready
kubectl get pods -A    # kube-system pods Running
kubectl get ingress    # web ingress (after deploying samples)
kubectl get pvc         # bound PersistentVolumeClaims
```

Cluster components specifically:

```bash
kubectl -n kube-system get deploy coredns traefik local-path-provisioner
kubectl get storageclass   # local-path (default)
```

---

## How to deploy the sample applications

The examples live at `~/cluster/manifests/` inside WSL:

```bash
wsl -d Ubuntu
kubectl apply -f ~/cluster/manifests/
kubectl -n apps get pods -w
```

Included manifests (sized for a 16 GB machine):

| File | What |
|---|---|
| `00-namespace.yaml` | `apps` namespace |
| `05-secrets.yaml` | demo DB/Redis credentials + DSNs — **change these** |
| `10-postgres.yaml` | PostgreSQL **StatefulSet** + headless Service + 8Gi PVC (local-path) |
| `20-redis.yaml` | Redis **Deployment** + Service + 1Gi PVC |
| `30-web.yaml` | sample web **Deployment** (2 replicas) + Service |
| `40-huey-worker.yaml` | Huey **worker Deployment** (2 replicas, no ingress) |
| `50-ingress.yaml` | Traefik **Ingress** for `web.local` |

Replace the placeholder images in `30-web.yaml` (`traefik/whoami`) and
`40-huey-worker.yaml` (`python:3.12-slim`) with your own app image, and update
credentials in `05-secrets.yaml`.

### Reaching services from your LAN

The installer prints this machine's LAN IP. On any client, map the ingress host
to that IP (hosts file or DNS), e.g. add to the client's hosts file:

```
192.168.x.y   web.local
```

then browse `http://web.local/`. Traefik routes it to the `web` Service.

> **Approximate resource use** of the samples: requests total ~0.9 vCPU / ~1.5 GB —
> well within the 6 GB / 6 vCPU VM budget, leaving headroom for your real workloads.

---

## How to uninstall everything cleanly

```powershell
# 1) Remove sample workloads (optional; inside WSL)
wsl -d Ubuntu -- kubectl delete -f /home/<user>/cluster/manifests/

# 2) Uninstall k3s (inside WSL)
wsl -d Ubuntu -u root -- /usr/local/bin/k3s-uninstall.sh

# 3) Remove LAN plumbing (elevated PowerShell)
netsh interface portproxy delete v4tov4 listenport=80  listenaddress=0.0.0.0
netsh interface portproxy delete v4tov4 listenport=443 listenaddress=0.0.0.0
Get-NetFirewallRule -DisplayName 'k3s WSL ingress *' | Remove-NetFirewallRule
Unregister-ScheduledTask -TaskName K3sPortProxyRefresh -Confirm:$false
Unregister-ScheduledTask -TaskName K3sSetupResume      -Confirm:$false -ErrorAction SilentlyContinue

# 4) Remove the whole Ubuntu distro (destroys the cluster + data)
wsl --unregister Ubuntu

# 5) Remove Windows-side artifacts
Remove-Item "$env:USERPROFILE\.kube\config" -ErrorAction SilentlyContinue
Remove-Item "$env:USERPROFILE\k3s-setup" -Recurse -Force -ErrorAction SilentlyContinue
[Environment]::SetEnvironmentVariable('KUBECONFIG', $null, 'User')
# Optional: delete or restore $env:USERPROFILE\.wslconfig

# 6) (Optional) disable the Windows features
Disable-WindowsOptionalFeature -Online -FeatureName VirtualMachinePlatform -NoRestart
Disable-WindowsOptionalFeature -Online -FeatureName Microsoft-Windows-Subsystem-Linux -NoRestart
```

---

## Troubleshooting

- **`kubectl` from PowerShell can't connect** — ensure WSL is running
  (`wsl -l -v`) and `KUBECONFIG` points at `%USERPROFILE%\.kube\config`. Open a
  new shell so the env var loads.
- **LAN clients can't reach `web.local`** — the WSL IP changed; run the refresh
  task manually: `Start-ScheduledTask -TaskName K3sPortProxyRefresh`, or re-run
  `.\Install-K3sCluster.ps1 -Stage Cluster`.
- **k3s not up after a Windows reboot** — WSL starts lazily; run any `wsl`
  command (or `wsl -d Ubuntu -u root -- systemctl start k3s`).
- **Pods stuck `Pending` on storage** — check the provisioner:
  `kubectl -n kube-system logs deploy/local-path-provisioner`.
- **Full log** — `%USERPROFILE%\k3s-setup\install.log`.
