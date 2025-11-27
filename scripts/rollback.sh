#!/usr/bin/env bash
# Quick Rollback Script for K8s Deployments
# Supports blue/green and canary rollback scenarios

set -euo pipefail

NAMESPACE="${NAMESPACE:-default}"
MODE="${1:-}"
TARGET="${2:-}"

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
Quick Rollback Script

Usage: $0 <mode> [target]

Modes:
  blue-green <color>   Rollback blue/green deployment to specified color
  canary               Rollback canary deployment (route all to stable)
  standard <name>      Rollback standard deployment to previous revision

Environment Variables:
  NAMESPACE   Kubernetes namespace (default: default)

Examples:
  # Rollback blue/green to blue
  $0 blue-green blue

  # Rollback canary deployment
  $0 canary

  # Rollback standard deployment
  $0 standard agentic-ai

EOF
  exit 1
}

rollback_blue_green() {
  local color=$1

  if [[ "$color" != "blue" && "$color" != "green" ]]; then
    log_error "Color must be 'blue' or 'green'"
    exit 1
  fi

  log_warning "Rolling back blue/green deployment to $color"

  # Get current service configuration
  local current=$(kubectl get svc agentic-ai -n "$NAMESPACE" \
    -o jsonpath='{.spec.selector.version}' 2>/dev/null || echo "")

  if [[ "$current" == "$color" ]]; then
    log_warning "Service already pointing to $color"
    exit 0
  fi

  log_info "Current color: $current"
  log_info "Target color: $color"

  # Verify target deployment is healthy
  local ready=$(kubectl get deployment "agentic-ai-${color}" -n "$NAMESPACE" \
    -o jsonpath='{.status.readyReplicas}' 2>/dev/null || echo "0")
  local desired=$(kubectl get deployment "agentic-ai-${color}" -n "$NAMESPACE" \
    -o jsonpath='{.spec.replicas}' 2>/dev/null || echo "0")

  if [[ "$ready" != "$desired" || "$ready" == "0" ]]; then
    log_error "Target deployment not healthy (ready: $ready, desired: $desired)"
    log_warning "Attempting to scale up target deployment..."

    kubectl scale deployment "agentic-ai-${color}" -n "$NAMESPACE" --replicas=2
    kubectl rollout status deployment/"agentic-ai-${color}" -n "$NAMESPACE" --timeout=3m
  fi

  # Switch service
  log_info "Switching service to $color..."
  kubectl patch svc agentic-ai -n "$NAMESPACE" \
    -p "{\"spec\":{\"selector\":{\"version\":\"${color}\"}}}"

  log_success "Rollback completed! Traffic now routing to $color"

  # Verify endpoints
  sleep 3
  local endpoints=$(kubectl get endpoints agentic-ai -n "$NAMESPACE" \
    -o jsonpath='{.subsets[0].addresses[*].targetRef.name}')
  log_info "Active endpoints: $endpoints"
}

rollback_canary() {
  log_warning "Rolling back canary deployment - routing all traffic to stable"

  # Set canary weight to 0
  kubectl annotate ingress agentic-ai-canary \
    nginx.ingress.kubernetes.io/canary-weight="0" \
    -n "$NAMESPACE" --overwrite 2>/dev/null || true

  # Verify stable deployment is healthy
  local ready=$(kubectl get deployment agentic-ai-stable -n "$NAMESPACE" \
    -o jsonpath='{.status.readyReplicas}' 2>/dev/null || echo "0")

  if [[ "$ready" == "0" ]]; then
    log_error "Stable deployment has no ready replicas"
    exit 1
  fi

  log_success "Rollback completed! All traffic routed to stable"
  log_info "Canary deployment still running (0% traffic) for investigation"

  # Optionally scale down canary
  read -p "Scale down canary deployment to 0? (yes/no): " -r
  if [[ $REPLY =~ ^[Yy](es)?$ ]]; then
    kubectl scale deployment agentic-ai-canary -n "$NAMESPACE" --replicas=0
    log_success "Canary deployment scaled to 0"
  fi
}

rollback_standard() {
  local deployment=$1

  if [[ -z "$deployment" ]]; then
    log_error "Deployment name required"
    usage
  fi

  log_warning "Rolling back deployment: $deployment"

  # Get revision history
  log_info "Recent revisions:"
  kubectl rollout history deployment/"$deployment" -n "$NAMESPACE"

  echo ""
  read -p "Rollback to previous revision? (yes/no): " -r
  if [[ ! $REPLY =~ ^[Yy](es)?$ ]]; then
    log_warning "Rollback cancelled"
    exit 0
  fi

  # Perform rollback
  kubectl rollout undo deployment/"$deployment" -n "$NAMESPACE"

  log_info "Waiting for rollback to complete..."
  kubectl rollout status deployment/"$deployment" -n "$NAMESPACE" --timeout=5m

  log_success "Rollback completed successfully!"

  # Show new revision
  local new_revision=$(kubectl get deployment "$deployment" -n "$NAMESPACE" \
    -o jsonpath='{.metadata.annotations.deployment\.kubernetes\.io/revision}')
  log_info "Current revision: $new_revision"
}

# Main execution
if [[ -z "$MODE" ]]; then
  usage
fi

case "$MODE" in
  blue-green)
    if [[ -z "$TARGET" ]]; then
      log_error "Target color required for blue-green rollback"
      usage
    fi
    rollback_blue_green "$TARGET"
    ;;
  canary)
    rollback_canary
    ;;
  standard)
    if [[ -z "$TARGET" ]]; then
      log_error "Deployment name required for standard rollback"
      usage
    fi
    rollback_standard "$TARGET"
    ;;
  *)
    log_error "Invalid mode: $MODE"
    usage
    ;;
esac
