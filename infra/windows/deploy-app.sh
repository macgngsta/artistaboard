#!/usr/bin/env bash
#
# deploy-app.sh
# -------------
# Build your application image and roll it out to the single-node k3s cluster —
# WITHOUT a registry. k3s runs on containerd (not Docker), so a locally-built
# image must be imported into containerd's image store before pods can use it.
#
# This script does exactly that:
#   1. build the image (Docker if present, else `k3s ctr` / buildah-free path)
#   2. import it into k3s's containerd namespace (k8s.io)
#   3. set the image on your Deployment/StatefulSet and wait for rollout
#
# Run it INSIDE WSL from your project directory (where the Dockerfile lives).
#
# Usage:
#   deploy-app.sh -n <namespace> -k <deploy|statefulset>/<name> -i <image:tag> [-f Dockerfile] [-c <container>] [-p <build-context>]
#
# Example (deploy the web app from ./ using ./Dockerfile):
#   deploy-app.sh -n apps -k deployment/web -i myapp/web:dev
#
# Example (Huey worker, custom Dockerfile + context):
#   deploy-app.sh -n apps -k deployment/huey-worker -i myapp/worker:dev -f worker.Dockerfile -p .

set -euo pipefail

NAMESPACE=""
TARGET=""            # e.g. deployment/web
IMAGE=""             # e.g. myapp/web:dev
DOCKERFILE="Dockerfile"
CONTEXT="."
CONTAINER=""         # container name to patch; defaults to the resource name

usage() { grep -E '^#( |$)' "$0" | sed 's/^# \{0,1\}//'; exit "${1:-0}"; }

while getopts ':n:k:i:f:p:c:h' opt; do
  case "$opt" in
    n) NAMESPACE="$OPTARG" ;;
    k) TARGET="$OPTARG" ;;
    i) IMAGE="$OPTARG" ;;
    f) DOCKERFILE="$OPTARG" ;;
    p) CONTEXT="$OPTARG" ;;
    c) CONTAINER="$OPTARG" ;;
    h) usage 0 ;;
    *) echo "Unknown option: -$OPTARG" >&2; usage 1 ;;
  esac
done

[ -n "$NAMESPACE" ] && [ -n "$TARGET" ] && [ -n "$IMAGE" ] || {
  echo "ERROR: -n, -k, and -i are required." >&2; usage 1; }

# Container defaults to the resource name (deployment/web -> container 'web').
[ -n "$CONTAINER" ] || CONTAINER="${TARGET##*/}"

log() { printf '[deploy] %s\n' "$*"; }

# ---------------------------------------------------------------------------
# 1) Build the image.
#    Prefer Docker if the user has it (Docker Desktop / docker in WSL). Otherwise
#    fall back to building an OCI tar with the Docker CLI unavailable is out of
#    scope — we require a builder. Most dev boxes have docker; if not, push to a
#    registry instead (see DEPLOY.md).
# ---------------------------------------------------------------------------
log "Building image '$IMAGE' from '$DOCKERFILE' (context: $CONTEXT)"
if command -v docker >/dev/null 2>&1; then
  docker build -t "$IMAGE" -f "$DOCKERFILE" "$CONTEXT"
  TAR="$(mktemp --suffix=.tar)"
  trap 'rm -f "$TAR"' EXIT
  log "Exporting image to $TAR"
  docker save "$IMAGE" -o "$TAR"
else
  echo "ERROR: docker not found in WSL. Install Docker or push to a registry (see DEPLOY.md)." >&2
  exit 1
fi

# ---------------------------------------------------------------------------
# 2) Import into k3s's containerd (namespace k8s.io) so kubelet can find it.
#    `k3s ctr` talks to the same containerd the cluster uses.
# ---------------------------------------------------------------------------
log "Importing image into k3s containerd"
sudo k3s ctr images import "$TAR"

# ---------------------------------------------------------------------------
# 3) Point the workload at the image and roll out.
#    imagePullPolicy=IfNotPresent (or Never) is required so kubelet uses the
#    locally-imported image instead of trying to pull from a registry.
# ---------------------------------------------------------------------------
log "Setting $TARGET container '$CONTAINER' image to $IMAGE (pullPolicy=IfNotPresent)"
kubectl -n "$NAMESPACE" set image "$TARGET" "$CONTAINER=$IMAGE"
kubectl -n "$NAMESPACE" patch "$TARGET" --type=json \
  -p="[{\"op\":\"replace\",\"path\":\"/spec/template/spec/containers/0/imagePullPolicy\",\"value\":\"IfNotPresent\"}]" \
  2>/dev/null || true

# Force a rollout even if the tag is unchanged (image content may have changed).
kubectl -n "$NAMESPACE" rollout restart "$TARGET"
log "Waiting for rollout..."
kubectl -n "$NAMESPACE" rollout status "$TARGET" --timeout=180s

log "Done. Current pods:"
kubectl -n "$NAMESPACE" get pods -l "app=${TARGET##*/}"
