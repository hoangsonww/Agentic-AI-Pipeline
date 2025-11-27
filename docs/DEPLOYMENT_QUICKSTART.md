# Deployment Quick Start Guide

Quick reference for deploying with advanced strategies.

## Prerequisites

```bash
# Install required tools
brew install kubectl helm terraform flux argocd

# For AWS deployments
brew install awscli

# Verify installations
kubectl version --client
terraform version
flux --version
```

## Quick Deployment Commands

### Blue/Green Deployment (Kubernetes)

```bash
# 1. Apply infrastructure
kubectl apply -f k8s/blue-green/

# 2. Deploy to green
./scripts/blue_green_deploy.sh green agentic-ai:v1.2.0

# 3. Rollback if needed
./scripts/rollback.sh blue-green blue
```

### Canary Deployment (Kubernetes)

```bash
# 1. Apply infrastructure
kubectl apply -f k8s/canary/

# 2. Deploy canary
./scripts/canary_deploy.sh manual agentic-ai:v1.2.0

# 3. Rollback if needed
./scripts/rollback.sh canary
```

### Flagger Automated Canary

```bash
# 1. Install Flagger
kubectl apply -k github.com/fluxcd/flagger//kustomize/istio

# 2. Apply Flagger canary config
kubectl apply -f k8s/canary/flagger-canary.yaml

# 3. Deploy new version
kubectl set image deployment/agentic-ai app=agentic-ai:v1.2.0

# 4. Watch progress
kubectl describe canary agentic-ai --watch
```

### ArgoCD GitOps

```bash
# 1. Install ArgoCD
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml

# 2. Deploy application
kubectl apply -f gitops/argocd/application.yaml

# 3. Access UI
kubectl port-forward svc/argocd-server -n argocd 8080:443
# Username: admin
# Password: kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d
```

### Flux GitOps

```bash
# 1. Bootstrap Flux
flux bootstrap github \
  --owner=your-org \
  --repository=Research-Outreach-Agentic-AI \
  --branch=main \
  --path=gitops/flux

# 2. Apply sync configs
kubectl apply -f gitops/flux/gotk-sync.yaml
kubectl apply -f gitops/flux/canary-sync.yaml

# 3. Watch reconciliation
flux get kustomizations --watch
```

### ECS Blue/Green (AWS)

```bash
# 1. Deploy infrastructure with Terraform
cd hashicorp/terraform
terraform init
terraform apply -auto-approve

# 2. Deploy new version
AWS_REGION=us-west-2 ENV=prod ./scripts/ecs_blue_green_deploy.sh v1.2.0

# 3. Monitor deployment
aws deploy get-deployment --deployment-id <id>
```

## Monitoring Deployments

```bash
# Continuous health monitoring
ROLLBACK_ENABLED=true ./scripts/deployment_monitor.sh agentic-ai

# Watch pods
kubectl get pods -w

# Watch deployments
kubectl get deployments -w

# Check logs
kubectl logs -f deployment/agentic-ai

# Check metrics (if metrics-server installed)
kubectl top pods
```

## Emergency Rollback

```bash
# Kubernetes - rollback deployment
kubectl rollout undo deployment/agentic-ai

# Blue/Green - switch back
kubectl patch svc agentic-ai -p '{"spec":{"selector":{"version":"blue"}}}'

# Canary - set weight to 0
kubectl annotate ingress agentic-ai-canary \
  nginx.ingress.kubernetes.io/canary-weight="0" --overwrite

# ECS - stop deployment
aws deploy stop-deployment --deployment-id <id> --auto-rollback-enabled
```

## Environment Variables

```bash
# Kubernetes deployments
export NAMESPACE=default

# ECS deployments
export AWS_REGION=us-west-2
export APP_NAME=agentic-ai
export ENV=production

# Canary settings
export CANARY_WEIGHT=10

# Monitoring
export CHECK_INTERVAL=30
export ERROR_THRESHOLD=3
export ROLLBACK_ENABLED=true
```

## Common Workflows

### Promote Canary to Production

```bash
# 1. Deploy canary at 10%
./scripts/canary_deploy.sh manual agentic-ai:v2.0.0

# 2. Monitor for 5-10 minutes
./scripts/deployment_monitor.sh agentic-ai-canary

# 3. Increase to 50%
kubectl annotate ingress agentic-ai-canary \
  nginx.ingress.kubernetes.io/canary-weight="50" --overwrite

# 4. Monitor again

# 5. Full promotion
kubectl set image deployment/agentic-ai-stable app=agentic-ai:v2.0.0
kubectl annotate ingress agentic-ai-canary \
  nginx.ingress.kubernetes.io/canary-weight="0" --overwrite
```

### Blue/Green with Testing

```bash
# 1. Deploy to green
./scripts/blue_green_deploy.sh green agentic-ai:v2.0.0

# 2. Test green environment directly
kubectl port-forward deployment/agentic-ai-green 8001:8000
curl http://localhost:8001/api/new_chat

# 3. Run smoke tests
./scripts/smoke.sh http://localhost:8001

# 4. Switch traffic if tests pass
kubectl patch svc agentic-ai -p '{"spec":{"selector":{"version":"green"}}}'

# 5. Verify in production
curl http://<load-balancer-ip>/api/new_chat
```

## Troubleshooting Commands

```bash
# Check deployment status
kubectl rollout status deployment/agentic-ai

# View deployment history
kubectl rollout history deployment/agentic-ai

# Describe resources
kubectl describe deployment agentic-ai
kubectl describe pod <pod-name>
kubectl describe svc agentic-ai

# Check events
kubectl get events --sort-by='.lastTimestamp' | head -20

# Check Flagger status
kubectl get canary
kubectl describe canary agentic-ai

# Check ArgoCD sync status
kubectl get application -n argocd
argocd app get agentic-ai

# Check Flux reconciliation
flux get all
flux get kustomizations
```

## Best Practices Checklist

- [ ] Test deployment in staging first
- [ ] Review deployment plan with team
- [ ] Verify health checks are configured
- [ ] Ensure monitoring/alerts are active
- [ ] Have rollback plan ready
- [ ] Deploy during low-traffic window
- [ ] Monitor metrics continuously
- [ ] Keep old version running until confident
- [ ] Document any issues encountered
- [ ] Update runbooks if needed

## Quick Reference

| Strategy | Command | Rollback |
|----------|---------|----------|
| Blue/Green | `./scripts/blue_green_deploy.sh green <tag>` | `./scripts/rollback.sh blue-green blue` |
| Canary | `./scripts/canary_deploy.sh manual <tag>` | `./scripts/rollback.sh canary` |
| Flagger | `kubectl set image deployment/agentic-ai app=<tag>` | Automatic |
| Standard | `kubectl set image deployment/agentic-ai app=<tag>` | `kubectl rollout undo deployment/agentic-ai` |

## Getting Help

- Check logs: `kubectl logs deployment/agentic-ai`
- Describe resource: `kubectl describe <resource> <name>`
- Check events: `kubectl get events`
- Review documentation: `docs/ADVANCED_DEPLOYMENTS.md`
