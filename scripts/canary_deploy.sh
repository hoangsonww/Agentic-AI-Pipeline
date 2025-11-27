#!/usr/bin/env bash
# Canary Deployment Automation Script
# Supports both manual and automated (Flagger) canary deployments

set -euo pipefail

NAMESPACE="${NAMESPACE:-default}"
MODE="${1:-manual}"  # manual or flagger
NEW_IMAGE="${2:-}"
CANARY_WEIGHT="${CANARY_WEIGHT:-10}"  # Initial canary traffic percentage

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

usage() {
  cat <<EOF
Canary Deployment Script

Usage: $0 <mode> <image:tag> [options]

Modes:
  manual    Manual canary deployment with gradual traffic shifting
  flagger   Automated canary using Flagger (requires Flagger installed)

Arguments:
  image:tag   Docker image with tag to deploy

Environment Variables:
  NAMESPACE       Kubernetes namespace (default: default)
  CANARY_WEIGHT   Initial canary traffic % (default: 10)

Examples:
  # Manual canary with 10% initial traffic
  $0 manual agentic-ai:v1.2.0

  # Flagger automated canary
  $0 flagger agentic-ai:v1.2.0

  # Custom canary weight
  CANARY_WEIGHT=25 $0 manual agentic-ai:v1.2.0

Workflow (Manual):
  1. Deploy canary version alongside stable
  2. Route small % of traffic to canary
  3. Monitor metrics and errors
  4. Gradually increase canary traffic
  5. Promote or rollback based on metrics

Workflow (Flagger):
  1. Update image tag
  2. Flagger automatically manages progressive delivery
  3. Automated metrics analysis and rollback

EOF
  exit 1
}

if [[ -z "$MODE" || -z "$NEW_IMAGE" ]]; then
  usage
fi

# ============================================
# FLAGGER MODE
# ============================================
if [[ "$MODE" == "flagger" ]]; then
  log_info "Using Flagger automated canary deployment"

  # Check if Flagger is installed
  if ! kubectl get crd canaries.flagger.app &>/dev/null; then
    log_error "Flagger CRD not found. Install Flagger first:"
    echo "  kubectl apply -k github.com/fluxcd/flagger//kustomize/istio"
    exit 1
  fi

  log_info "Updating deployment image to $NEW_IMAGE"
  kubectl set image deployment/agentic-ai app="$NEW_IMAGE" -n "$NAMESPACE"

  log_info "Flagger will automatically manage the canary rollout"
  log_info "Monitor progress with: kubectl describe canary agentic-ai -n $NAMESPACE"

  # Watch canary status
  log_info "Watching canary progress (Ctrl+C to exit)..."
  kubectl get canary agentic-ai -n "$NAMESPACE" --watch

  exit 0
fi

# ============================================
# MANUAL MODE
# ============================================
if [[ "$MODE" != "manual" ]]; then
  log_error "Invalid mode: $MODE"
  usage
fi

log_info "Starting manual canary deployment"
log_info "New image: $NEW_IMAGE"
log_info "Initial canary weight: ${CANARY_WEIGHT}%"

# Step 1: Deploy canary
log_info "Step 1: Deploying canary version..."
kubectl set image deployment/agentic-ai-canary app="$NEW_IMAGE" -n "$NAMESPACE"

# Wait for canary rollout
log_info "Waiting for canary rollout..."
kubectl rollout status deployment/agentic-ai-canary -n "$NAMESPACE" --timeout=5m

# Step 2: Verify canary health
log_info "Step 2: Verifying canary health..."
CANARY_READY=$(kubectl get deployment agentic-ai-canary -n "$NAMESPACE" -o jsonpath='{.status.readyReplicas}')
if [[ "$CANARY_READY" -lt 1 ]]; then
  log_error "Canary deployment has no ready replicas"
  exit 1
fi
log_success "Canary has $CANARY_READY ready replicas"

# Step 3: Run smoke tests on canary
log_info "Step 3: Running smoke tests on canary..."
CANARY_POD=$(kubectl get pods -n "$NAMESPACE" -l "app=agentic-ai,track=canary" -o jsonpath='{.items[0].metadata.name}')

kubectl port-forward -n "$NAMESPACE" "$CANARY_POD" 8081:8000 &
PF_PID=$!
sleep 3

SMOKE_TEST=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8081/api/new_chat || echo "000")
kill $PF_PID 2>/dev/null || true

if [[ "$SMOKE_TEST" != "200" ]]; then
  log_error "Canary smoke test failed (HTTP $SMOKE_TEST)"
  exit 1
fi
log_success "Canary smoke test passed"

# Step 4: Update ingress to route traffic
log_info "Step 4: Routing ${CANARY_WEIGHT}% traffic to canary..."
kubectl annotate ingress agentic-ai-canary \
  nginx.ingress.kubernetes.io/canary-weight="${CANARY_WEIGHT}" \
  -n "$NAMESPACE" --overwrite

log_success "Initial canary traffic routing configured"

# Step 5: Progressive rollout
log_warning "Monitor canary metrics before proceeding"
cat <<EOF

${YELLOW}Monitoring Commands:${NC}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  # Pod metrics
  kubectl top pods -n $NAMESPACE -l app=agentic-ai

  # Logs comparison
  kubectl logs -n $NAMESPACE -l track=stable --tail=50
  kubectl logs -n $NAMESPACE -l track=canary --tail=50

  # Error rate (if Prometheus available)
  # rate(http_requests_total{status=~"5.."}[5m])

${GREEN}Progressive Rollout Steps:${NC}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
EOF

WEIGHTS=(10 25 50 75 100)
for weight in "${WEIGHTS[@]}"; do
  if [[ $weight -le $CANARY_WEIGHT ]]; then
    continue
  fi

  echo ""
  read -p "Increase canary to ${weight}%? (yes/no/rollback): " -r

  if [[ $REPLY =~ ^[Rr](ollback)?$ ]]; then
    log_warning "Rolling back canary deployment..."
    kubectl annotate ingress agentic-ai-canary \
      nginx.ingress.kubernetes.io/canary-weight="0" \
      -n "$NAMESPACE" --overwrite
    log_success "Traffic reverted to stable. Canary still running for investigation."
    exit 0
  fi

  if [[ ! $REPLY =~ ^[Yy](es)?$ ]]; then
    log_warning "Stopping at ${CANARY_WEIGHT}% canary traffic"
    exit 0
  fi

  log_info "Updating canary weight to ${weight}%..."
  kubectl annotate ingress agentic-ai-canary \
    nginx.ingress.kubernetes.io/canary-weight="${weight}" \
    -n "$NAMESPACE" --overwrite

  CANARY_WEIGHT=$weight
  log_success "Canary now receiving ${weight}% of traffic"

  if [[ $weight -lt 100 ]]; then
    log_info "Monitor for 2-5 minutes before proceeding..."
    sleep 10
  fi
done

# Step 6: Promote canary to stable
log_info "Step 6: Promoting canary to stable..."
CANARY_IMAGE=$(kubectl get deployment agentic-ai-canary -n "$NAMESPACE" -o jsonpath='{.spec.template.spec.containers[0].image}')

kubectl set image deployment/agentic-ai-stable app="$CANARY_IMAGE" -n "$NAMESPACE"
kubectl rollout status deployment/agentic-ai-stable -n "$NAMESPACE" --timeout=5m

# Step 7: Remove canary traffic routing
log_info "Step 7: Reverting to stable-only traffic..."
kubectl annotate ingress agentic-ai-canary \
  nginx.ingress.kubernetes.io/canary-weight="0" \
  -n "$NAMESPACE" --overwrite

log_success "Canary deployment completed successfully!"

cat <<EOF

${GREEN}Deployment Summary:${NC}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Promoted Image:  $CANARY_IMAGE
  Stable Version:  Updated to canary
  Canary Status:   Standby (0% traffic)
  Namespace:       $NAMESPACE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

${YELLOW}Cleanup:${NC}
  Once confident, scale down canary:
  kubectl scale deployment/agentic-ai-canary -n $NAMESPACE --replicas=0

EOF
