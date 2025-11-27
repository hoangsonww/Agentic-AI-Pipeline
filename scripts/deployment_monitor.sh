#!/usr/bin/env bash
# Deployment Monitoring and Health Check Script
# Monitors deployment health and triggers rollback if needed

set -euo pipefail

NAMESPACE="${NAMESPACE:-default}"
DEPLOYMENT="${1:-agentic-ai}"
CHECK_INTERVAL="${CHECK_INTERVAL:-30}"
ERROR_THRESHOLD="${ERROR_THRESHOLD:-3}"
ROLLBACK_ENABLED="${ROLLBACK_ENABLED:-false}"

RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

ERROR_COUNT=0
PREVIOUS_REVISION=""

usage() {
  cat <<EOF
Deployment Monitoring Script

Usage: $0 <deployment-name> [options]

Arguments:
  deployment-name   Name of the deployment to monitor

Environment Variables:
  NAMESPACE          Kubernetes namespace (default: default)
  CHECK_INTERVAL     Health check interval in seconds (default: 30)
  ERROR_THRESHOLD    Number of failures before alert/rollback (default: 3)
  ROLLBACK_ENABLED   Enable automatic rollback (default: false)

Examples:
  # Monitor deployment
  $0 agentic-ai-blue

  # Monitor with auto-rollback
  ROLLBACK_ENABLED=true $0 agentic-ai-canary

Monitors:
  - Pod readiness and health
  - Resource utilization
  - Error rates in logs
  - Service endpoint health
  - Deployment progress

EOF
  exit 1
}

check_pod_health() {
  local deployment=$1

  # Get pod status
  local ready_pods=$(kubectl get deployment "$deployment" -n "$NAMESPACE" \
    -o jsonpath='{.status.readyReplicas}' 2>/dev/null || echo "0")
  local desired_pods=$(kubectl get deployment "$deployment" -n "$NAMESPACE" \
    -o jsonpath='{.spec.replicas}' 2>/dev/null || echo "0")
  local unavailable=$(kubectl get deployment "$deployment" -n "$NAMESPACE" \
    -o jsonpath='{.status.unavailableReplicas}' 2>/dev/null || echo "0")

  if [[ "$ready_pods" -lt "$desired_pods" ]]; then
    log_warning "Pods not ready: $ready_pods/$desired_pods"
    return 1
  fi

  if [[ "$unavailable" -gt 0 ]]; then
    log_warning "Unavailable pods: $unavailable"
    return 1
  fi

  log_success "Pod health OK: $ready_pods/$desired_pods ready"
  return 0
}

check_service_health() {
  local deployment=$1
  local app_label=$(kubectl get deployment "$deployment" -n "$NAMESPACE" \
    -o jsonpath='{.spec.selector.matchLabels.app}' 2>/dev/null || echo "")

  if [[ -z "$app_label" ]]; then
    log_warning "Could not determine app label"
    return 1
  fi

  # Get a pod from the deployment
  local pod=$(kubectl get pods -n "$NAMESPACE" -l "app=$app_label" \
    -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")

  if [[ -z "$pod" ]]; then
    log_error "No pods found for deployment"
    return 1
  fi

  # Port forward and health check
  kubectl port-forward -n "$NAMESPACE" "$pod" 9090:8000 >/dev/null 2>&1 &
  local pf_pid=$!
  sleep 2

  local status=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:9090/api/new_chat 2>/dev/null || echo "000")
  kill $pf_pid 2>/dev/null || true

  if [[ "$status" == "200" ]]; then
    log_success "Service health OK (HTTP $status)"
    return 0
  else
    log_error "Service health check failed (HTTP $status)"
    return 1
  fi
}

check_error_logs() {
  local deployment=$1
  local app_label=$(kubectl get deployment "$deployment" -n "$NAMESPACE" \
    -o jsonpath='{.spec.selector.matchLabels.app}' 2>/dev/null || echo "")

  if [[ -z "$app_label" ]]; then
    return 0
  fi

  # Check for errors in recent logs
  local error_count=$(kubectl logs -n "$NAMESPACE" -l "app=$app_label" \
    --since=60s 2>/dev/null | grep -i "error\|exception\|fatal" | wc -l || echo "0")

  if [[ "$error_count" -gt 5 ]]; then
    log_warning "High error rate detected: $error_count errors in last 60s"
    return 1
  fi

  log_success "Log error rate OK: $error_count errors"
  return 0
}

check_resource_usage() {
  local deployment=$1

  # Get pods for the deployment
  local app_label=$(kubectl get deployment "$deployment" -n "$NAMESPACE" \
    -o jsonpath='{.spec.selector.matchLabels.app}' 2>/dev/null || echo "")

  if [[ -z "$app_label" ]]; then
    return 0
  fi

  # Get resource usage
  local metrics=$(kubectl top pods -n "$NAMESPACE" -l "app=$app_label" 2>/dev/null || echo "")

  if [[ -z "$metrics" ]]; then
    log_warning "Unable to fetch metrics (metrics-server required)"
    return 0
  fi

  # Parse CPU and memory usage (simple threshold check)
  local high_cpu=$(echo "$metrics" | awk '{if ($2 ~ /[0-9]+m/ && $2+0 > 400) print $1}')
  local high_mem=$(echo "$metrics" | awk '{if ($3 ~ /[0-9]+Mi/ && $3+0 > 800) print $1}')

  if [[ -n "$high_cpu" ]]; then
    log_warning "High CPU usage detected in pods: $high_cpu"
  fi

  if [[ -n "$high_mem" ]]; then
    log_warning "High memory usage detected in pods: $high_mem"
  fi

  if [[ -z "$high_cpu" && -z "$high_mem" ]]; then
    log_success "Resource usage OK"
  fi

  return 0
}

trigger_rollback() {
  local deployment=$1

  log_error "Health checks failed $ERROR_THRESHOLD times consecutively"

  if [[ "$ROLLBACK_ENABLED" == "true" ]]; then
    log_warning "Triggering automatic rollback..."

    # Rollback to previous revision
    kubectl rollout undo deployment/"$deployment" -n "$NAMESPACE"

    log_info "Waiting for rollback to complete..."
    kubectl rollout status deployment/"$deployment" -n "$NAMESPACE" --timeout=5m

    log_success "Rollback completed"

    # Send alert (customize based on your alerting system)
    log_warning "ALERT: Deployment $deployment was automatically rolled back due to health check failures"
  else
    log_error "Automatic rollback disabled. Manual intervention required."
    log_warning "To rollback manually, run:"
    echo "  kubectl rollout undo deployment/$deployment -n $NAMESPACE"
  fi
}

monitor_deployment() {
  local deployment=$1

  log_info "Starting continuous monitoring of deployment: $deployment"
  log_info "Namespace: $NAMESPACE"
  log_info "Check interval: ${CHECK_INTERVAL}s"
  log_info "Error threshold: $ERROR_THRESHOLD"
  log_info "Auto-rollback: $ROLLBACK_ENABLED"
  echo ""

  while true; do
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "$(date '+%Y-%m-%d %H:%M:%S') - Health Check"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    local all_healthy=true

    # Run health checks
    check_pod_health "$deployment" || all_healthy=false
    check_service_health "$deployment" || all_healthy=false
    check_error_logs "$deployment" || all_healthy=false
    check_resource_usage "$deployment"

    # Track deployment revision
    local current_revision=$(kubectl get deployment "$deployment" -n "$NAMESPACE" \
      -o jsonpath='{.metadata.annotations.deployment\.kubernetes\.io/revision}' 2>/dev/null || echo "")

    if [[ -n "$current_revision" && "$current_revision" != "$PREVIOUS_REVISION" ]]; then
      log_info "Deployment revision changed: $PREVIOUS_REVISION -> $current_revision"
      PREVIOUS_REVISION="$current_revision"
      ERROR_COUNT=0
    fi

    # Handle health check results
    if [[ "$all_healthy" == "false" ]]; then
      ERROR_COUNT=$((ERROR_COUNT + 1))
      log_warning "Health check failed (failure count: $ERROR_COUNT/$ERROR_THRESHOLD)"

      if [[ $ERROR_COUNT -ge $ERROR_THRESHOLD ]]; then
        trigger_rollback "$deployment"
        break
      fi
    else
      if [[ $ERROR_COUNT -gt 0 ]]; then
        log_info "Health recovered, resetting error count"
      fi
      ERROR_COUNT=0
    fi

    echo ""
    sleep "$CHECK_INTERVAL"
  done
}

# Main execution
if [[ -z "$DEPLOYMENT" ]]; then
  usage
fi

# Verify deployment exists
if ! kubectl get deployment "$DEPLOYMENT" -n "$NAMESPACE" &>/dev/null; then
  log_error "Deployment '$DEPLOYMENT' not found in namespace '$NAMESPACE'"
  exit 1
fi

# Start monitoring
monitor_deployment "$DEPLOYMENT"
