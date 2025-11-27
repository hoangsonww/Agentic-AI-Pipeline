#!/usr/bin/env bash
# Blue/Green Deployment Automation Script
# Usage: ./blue_green_deploy.sh [blue|green] [image:tag]

set -euo pipefail

NAMESPACE="${NAMESPACE:-default}"
NEW_COLOR="${1:-}"
NEW_IMAGE="${2:-}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

usage() {
  cat <<EOF
Blue/Green Deployment Script

Usage: $0 <blue|green> <image:tag>

Arguments:
  color       Target deployment color (blue or green)
  image:tag   Docker image with tag to deploy

Environment Variables:
  NAMESPACE   Kubernetes namespace (default: default)

Examples:
  $0 green agentic-ai:v1.2.0
  NAMESPACE=production $0 blue agentic-ai:latest

Workflow:
  1. Deploy new version to inactive environment (blue/green)
  2. Wait for pods to be ready
  3. Run health checks
  4. Switch traffic to new environment
  5. Keep old environment for quick rollback

EOF
  exit 1
}

# Validate arguments
if [[ -z "$NEW_COLOR" || -z "$NEW_IMAGE" ]]; then
  usage
fi

if [[ "$NEW_COLOR" != "blue" && "$NEW_COLOR" != "green" ]]; then
  log_error "Color must be 'blue' or 'green'"
  usage
fi

# Determine current and new environments
CURRENT_COLOR=$(kubectl get svc agentic-ai -n "$NAMESPACE" -o jsonpath='{.spec.selector.version}' 2>/dev/null || echo "none")
log_info "Current active color: $CURRENT_COLOR"
log_info "Deploying to color: $NEW_COLOR"
log_info "New image: $NEW_IMAGE"

# Step 1: Update deployment with new image
log_info "Step 1: Updating deployment-${NEW_COLOR} with image $NEW_IMAGE"
kubectl set image deployment/agentic-ai-${NEW_COLOR} \
  app="$NEW_IMAGE" \
  -n "$NAMESPACE"

# Step 2: Wait for rollout to complete
log_info "Step 2: Waiting for rollout to complete..."
kubectl rollout status deployment/agentic-ai-${NEW_COLOR} -n "$NAMESPACE" --timeout=5m

# Step 3: Verify pods are ready
log_info "Step 3: Verifying pods are ready..."
READY_PODS=$(kubectl get deployment agentic-ai-${NEW_COLOR} -n "$NAMESPACE" -o jsonpath='{.status.readyReplicas}')
DESIRED_PODS=$(kubectl get deployment agentic-ai-${NEW_COLOR} -n "$NAMESPACE" -o jsonpath='{.spec.replicas}')

if [[ "$READY_PODS" != "$DESIRED_PODS" ]]; then
  log_error "Pods not ready. Ready: $READY_PODS, Desired: $DESIRED_PODS"
  exit 1
fi

log_success "All $READY_PODS pods are ready"

# Step 4: Run health checks
log_info "Step 4: Running health checks..."
POD_NAME=$(kubectl get pods -n "$NAMESPACE" -l "app=agentic-ai,version=${NEW_COLOR}" -o jsonpath='{.items[0].metadata.name}')

# Port forward to pod for health check
kubectl port-forward -n "$NAMESPACE" "$POD_NAME" 8080:8000 &
PF_PID=$!
sleep 3

# Health check
HEALTH_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/api/new_chat || echo "000")
kill $PF_PID 2>/dev/null || true

if [[ "$HEALTH_STATUS" != "200" ]]; then
  log_error "Health check failed with status: $HEALTH_STATUS"
  log_warning "Deployment completed but not switching traffic due to failed health check"
  exit 1
fi

log_success "Health check passed (HTTP $HEALTH_STATUS)"

# Step 5: Ask for confirmation before switching traffic
log_warning "Ready to switch traffic from '$CURRENT_COLOR' to '$NEW_COLOR'"
read -p "Continue with traffic switch? (yes/no): " -r
if [[ ! $REPLY =~ ^[Yy](es)?$ ]]; then
  log_warning "Traffic switch cancelled by user"
  exit 0
fi

# Step 6: Switch service selector to new color
log_info "Step 6: Switching traffic to $NEW_COLOR environment..."
kubectl patch svc agentic-ai -n "$NAMESPACE" -p "{\"spec\":{\"selector\":{\"version\":\"${NEW_COLOR}\"}}}"

# Step 7: Verify service is routing to new pods
sleep 5
NEW_ENDPOINTS=$(kubectl get endpoints agentic-ai -n "$NAMESPACE" -o jsonpath='{.subsets[0].addresses[*].targetRef.name}')
log_info "Service now routing to pods: $NEW_ENDPOINTS"

# Step 8: Final verification
log_info "Step 8: Running final verification..."
SVC_IP=$(kubectl get svc agentic-ai -n "$NAMESPACE" -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || echo "")
if [[ -n "$SVC_IP" ]]; then
  FINAL_CHECK=$(curl -s -o /dev/null -w "%{http_code}" "http://${SVC_IP}/api/new_chat" || echo "000")
  if [[ "$FINAL_CHECK" == "200" ]]; then
    log_success "Final verification passed (HTTP $FINAL_CHECK)"
  else
    log_warning "Final verification returned HTTP $FINAL_CHECK"
  fi
fi

log_success "Blue/Green deployment completed successfully!"
log_info "Active environment: $NEW_COLOR"
log_info "Inactive environment: $CURRENT_COLOR (kept for quick rollback)"

cat <<EOF

${GREEN}Deployment Summary:${NC}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  New Image:     $NEW_IMAGE
  Active Color:  $NEW_COLOR
  Old Color:     $CURRENT_COLOR (standby)
  Namespace:     $NAMESPACE
  Ready Pods:    $READY_PODS/$DESIRED_PODS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

${YELLOW}Rollback Command:${NC}
  If issues are detected, rollback with:
  kubectl patch svc agentic-ai -n $NAMESPACE -p '{"spec":{"selector":{"version":"$CURRENT_COLOR"}}}'

${YELLOW}Cleanup Command:${NC}
  Once confident, scale down old environment:
  kubectl scale deployment/agentic-ai-$CURRENT_COLOR -n $NAMESPACE --replicas=0

EOF
