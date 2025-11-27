# Advanced Deployment Strategies

This document describes the advanced deployment and DevOps capabilities implemented for the Agentic AI application.

## Table of Contents

- [Overview](#overview)
- [Blue/Green Deployments](#bluegreen-deployments)
- [Canary Deployments](#canary-deployments)
- [GitOps with ArgoCD](#gitops-with-argocd)
- [GitOps with Flux](#gitops-with-flux)
- [Deployment Automation](#deployment-automation)
- [Monitoring and Rollback](#monitoring-and-rollback)
- [Infrastructure as Code](#infrastructure-as-code)
- [Best Practices](#best-practices)

## Overview

The deployment infrastructure supports multiple advanced deployment strategies:

- **Blue/Green Deployments**: Zero-downtime deployments with instant rollback capability
- **Canary Deployments**: Progressive rollouts with automated traffic shifting
- **GitOps**: Declarative, Git-driven deployments with ArgoCD and Flux
- **Automated Monitoring**: Continuous health checks with auto-rollback
- **Infrastructure as Code**: Terraform modules for AWS ECS with CodeDeploy

## Blue/Green Deployments

Blue/Green deployment maintains two identical production environments (blue and green), allowing instant switching between versions.

### Kubernetes Implementation

**Files:**
- `k8s/blue-green/deployment-blue.yaml`
- `k8s/blue-green/deployment-green.yaml`
- `k8s/blue-green/service.yaml`
- `k8s/blue-green/pvc.yaml`

**Deployment Script:**
```bash
./scripts/blue_green_deploy.sh <blue|green> <image:tag>
```

**Example:**
```bash
# Deploy new version to green environment
./scripts/blue_green_deploy.sh green agentic-ai:v1.2.0

# Script will:
# 1. Update green deployment with new image
# 2. Wait for rollout completion
# 3. Run health checks
# 4. Prompt for traffic switch
# 5. Update service selector to route to green
```

**Manual Operations:**
```bash
# Apply blue/green infrastructure
kubectl apply -f k8s/blue-green/

# Switch traffic to green
kubectl patch svc agentic-ai -n default \
  -p '{"spec":{"selector":{"version":"green"}}}'

# Rollback to blue
kubectl patch svc agentic-ai -n default \
  -p '{"spec":{"selector":{"version":"blue"}}}'
```

### ECS Blue/Green with CodeDeploy

**Terraform Module:** `hashicorp/terraform/modules/ecs_blue_green/`

Features:
- Dual target groups (blue/green)
- CodeDeploy integration
- Automated traffic switching
- Test listener on port 8080

**Deployment:**
```bash
# Deploy via CodeDeploy
AWS_REGION=us-west-2 ENV=prod ./scripts/ecs_blue_green_deploy.sh v1.2.0

# Script automatically:
# 1. Creates new task definition
# 2. Generates AppSpec
# 3. Triggers CodeDeploy deployment
# 4. Monitors progress
# 5. Reports status
```

**Terraform Apply:**
```bash
cd hashicorp/terraform
terraform init
terraform apply \
  -var="image_tag=v1.2.0" \
  -var="env=prod"
```

## Canary Deployments

Canary deployments gradually shift traffic from stable to new version, allowing early detection of issues.

### Native Kubernetes Canary

**Files:**
- `k8s/canary/deployment-stable.yaml`
- `k8s/canary/deployment-canary.yaml`
- `k8s/canary/ingress-canary.yaml`
- `k8s/canary/service-stable.yaml`
- `k8s/canary/service-canary.yaml`

**Using NGINX Ingress Controller:**
```bash
# Deploy canary with 10% traffic
kubectl apply -f k8s/canary/

# Adjust canary weight
kubectl annotate ingress agentic-ai-canary \
  nginx.ingress.kubernetes.io/canary-weight="25" --overwrite

# Promote to 100%
kubectl annotate ingress agentic-ai-canary \
  nginx.ingress.kubernetes.io/canary-weight="100" --overwrite
```

**Automated Script:**
```bash
# Manual canary with progressive rollout
./scripts/canary_deploy.sh manual agentic-ai:v1.2.0

# Flagger automated canary
./scripts/canary_deploy.sh flagger agentic-ai:v1.2.0
```

### Flagger Automated Canary

**Configuration:** `k8s/canary/flagger-canary.yaml`

Features:
- Automated progressive traffic shifting (10% → 25% → 50%)
- Prometheus metrics analysis
- Load testing during rollout
- Auto-rollback on failures

**Install Flagger:**
```bash
kubectl apply -k github.com/fluxcd/flagger//kustomize/istio

# Or for NGINX
helm upgrade -i flagger flagger/flagger \
  --namespace=flagger-system \
  --set meshProvider=nginx
```

**Deploy Canary:**
```bash
kubectl apply -f k8s/canary/flagger-canary.yaml

# Update deployment to trigger canary
kubectl set image deployment/agentic-ai app=agentic-ai:v1.2.0

# Monitor progress
kubectl describe canary agentic-ai
watch kubectl get canary agentic-ai
```

### ECS Canary with Weighted Target Groups

**Terraform Module:** `hashicorp/terraform/modules/ecs_canary/`

Features:
- Weighted ALB target groups
- Separate stable and canary services
- Configurable traffic distribution

```bash
cd hashicorp/terraform
terraform apply \
  -var="stable_image_tag=v1.1.0" \
  -var="canary_image_tag=v1.2.0" \
  -var="canary_weight=10"
```

## GitOps with ArgoCD

ArgoCD provides declarative, Git-driven continuous deployment.

### Installation

```bash
kubectl create namespace argocd
kubectl apply -n argocd -f \
  https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml

# Access UI
kubectl port-forward svc/argocd-server -n argocd 8080:443
```

### Applications

**Standard Application:**
```bash
kubectl apply -f gitops/argocd/application.yaml
```

**Blue/Green Application:**
```bash
kubectl apply -f gitops/argocd/application-blue-green.yaml
```

**Canary Application:**
```bash
kubectl apply -f gitops/argocd/application-canary.yaml
```

**App Project:**
```bash
kubectl apply -f gitops/argocd/appproject.yaml
```

### Argo Rollouts

Advanced progressive delivery with analysis:

```bash
kubectl create namespace argo-rollouts
kubectl apply -n argo-rollouts -f \
  https://github.com/argoproj/argo-rollouts/releases/latest/download/install.yaml

# Apply rollout strategy
kubectl apply -f gitops/argocd/rollout-strategy.yaml
```

**Monitor Rollouts:**
```bash
kubectl argo rollouts get rollout agentic-ai-rollout --watch
kubectl argo rollouts promote agentic-ai-rollout
kubectl argo rollouts abort agentic-ai-rollout
```

## GitOps with Flux

Flux v2 provides automated GitOps with image scanning and updates.

### Installation

```bash
flux install

# Bootstrap with GitHub
flux bootstrap github \
  --owner=your-org \
  --repository=Research-Outreach-Agentic-AI \
  --branch=main \
  --path=gitops/flux \
  --personal
```

### Sync Configuration

```bash
# Apply GitRepository source
kubectl apply -f gitops/flux/gotk-sync.yaml

# Apply Kustomizations
kubectl apply -f gitops/flux/blue-green-sync.yaml
kubectl apply -f gitops/flux/canary-sync.yaml
```

### Image Automation

Flux can automatically detect and deploy new images:

```bash
kubectl apply -f gitops/flux/image-automation.yaml

# Flux will:
# 1. Scan ECR for new images
# 2. Update manifests in Git
# 3. Sync to cluster automatically
```

### Notifications

```bash
# Create Slack webhook secret
kubectl create secret generic slack-webhook-url \
  -n flux-system \
  --from-literal=address=https://hooks.slack.com/services/YOUR/WEBHOOK/URL

# Apply notification configuration
kubectl apply -f gitops/flux/notification.yaml
```

## Deployment Automation

### Blue/Green Script

```bash
./scripts/blue_green_deploy.sh <color> <image:tag>
```

**Features:**
- Automated health checks
- Service endpoint verification
- Confirmation prompts
- Rollback instructions

### Canary Script

```bash
./scripts/canary_deploy.sh <manual|flagger> <image:tag>
```

**Features:**
- Progressive traffic shifting
- Smoke tests
- Metrics monitoring
- Auto-promotion workflow

### ECS Blue/Green Script

```bash
AWS_REGION=us-west-2 APP_NAME=agentic-ai ENV=prod \
  ./scripts/ecs_blue_green_deploy.sh v1.2.0
```

**Features:**
- Task definition updates
- CodeDeploy integration
- Deployment monitoring
- Status reporting

## Monitoring and Rollback

### Deployment Monitor

Continuous health monitoring with auto-rollback:

```bash
# Monitor with auto-rollback enabled
ROLLBACK_ENABLED=true ./scripts/deployment_monitor.sh agentic-ai-green

# Monitor without auto-rollback
./scripts/deployment_monitor.sh agentic-ai-canary
```

**Monitors:**
- Pod readiness and availability
- Service endpoint health
- Error rates in logs
- Resource utilization (CPU/memory)
- Deployment revision changes

**Auto-rollback triggers:**
- 3 consecutive health check failures
- High error rates in logs
- Pod crash loops

### Quick Rollback

```bash
# Blue/Green rollback
./scripts/rollback.sh blue-green blue

# Canary rollback (set traffic to 0%)
./scripts/rollback.sh canary

# Standard deployment rollback
./scripts/rollback.sh standard agentic-ai
```

**Manual Rollback:**
```bash
# Kubernetes
kubectl rollout undo deployment/agentic-ai

# ECS CodeDeploy
aws deploy stop-deployment \
  --deployment-id d-XXXXXXXXX \
  --auto-rollback-enabled
```

## Infrastructure as Code

### Terraform Modules

**Blue/Green ECS Module:**
```hcl
module "agentic_ai_bg" {
  source = "./modules/ecs_blue_green"

  app_name        = "agentic-ai"
  env             = "production"
  vpc_id          = var.vpc_id
  public_subnets  = var.public_subnets
  private_subnets = var.private_subnets
  aws_region      = "us-west-2"
  image_tag       = "v1.2.0"
  desired_count   = 3
}
```

**Canary ECS Module:**
```hcl
module "agentic_ai_canary" {
  source = "./modules/ecs_canary"

  app_name             = "agentic-ai"
  env                  = "production"
  stable_image_tag     = "v1.1.0"
  canary_image_tag     = "v1.2.0"
  canary_weight        = 10
  desired_count_stable = 3
  desired_count_canary = 1
}
```

### Outputs

Both modules provide:
- ALB DNS name
- ECR repository URL
- ECS cluster and service names
- CodeDeploy app/deployment group (blue/green only)

## Best Practices

### Pre-Deployment

1. **Test in staging** with identical deployment strategy
2. **Run smoke tests** on new version
3. **Review metrics** from previous deployment
4. **Prepare rollback plan** and verify rollback capability
5. **Communicate** with team about deployment window

### During Deployment

1. **Monitor metrics** continuously
   - Response times
   - Error rates
   - Resource usage
2. **Watch logs** for errors/warnings
3. **Verify health checks** pass consistently
4. **Gradual traffic shift** for canary (10% → 25% → 50% → 100%)
5. **Keep previous version** running until confident

### Post-Deployment

1. **Monitor for 15-30 minutes** after full rollout
2. **Check error tracking** (Sentry, Rollbar, etc.)
3. **Review metrics** compared to baseline
4. **Document issues** encountered
5. **Scale down old version** only after validation
6. **Update runbooks** if procedures changed

### Rollback Criteria

Trigger rollback if:
- Error rate increases >2x baseline
- P99 latency increases >50%
- Health checks fail consistently
- Critical bugs discovered
- Resource exhaustion detected

### Security

1. **Use secrets management** (Sealed Secrets, External Secrets Operator)
2. **Enable RBAC** for ArgoCD/Flux
3. **Scan images** before deployment (Trivy, Snyk)
4. **Audit deployments** with proper logging
5. **Restrict deployment windows** for production

### Observability

Required for advanced deployments:
- **Metrics**: Prometheus + Grafana
- **Logs**: ELK/Loki stack
- **Traces**: Jaeger/Tempo
- **Alerts**: AlertManager + PagerDuty/Slack
- **Dashboards**: Deployment-specific Grafana dashboards

## Troubleshooting

### Blue/Green Issues

**Problem:** Service not routing to new environment
```bash
# Check service selector
kubectl get svc agentic-ai -o yaml | grep -A 2 selector

# Verify endpoints
kubectl get endpoints agentic-ai

# Check pod labels
kubectl get pods --show-labels
```

**Problem:** Pods not ready
```bash
# Check pod status
kubectl describe pod <pod-name>

# Check logs
kubectl logs <pod-name>

# Check events
kubectl get events --sort-by='.lastTimestamp'
```

### Canary Issues

**Problem:** Flagger not progressing
```bash
# Check Flagger status
kubectl describe canary agentic-ai

# Check metrics server
kubectl get canary agentic-ai -o yaml

# View Flagger logs
kubectl logs -n flagger-system deployment/flagger
```

**Problem:** Ingress not routing correctly
```bash
# Verify ingress annotations
kubectl get ingress agentic-ai-canary -o yaml

# Check NGINX ingress controller logs
kubectl logs -n ingress-nginx deployment/ingress-nginx-controller
```

### GitOps Issues

**Problem:** ArgoCD app out of sync
```bash
# Check sync status
kubectl get application agentic-ai -n argocd

# Force sync
argocd app sync agentic-ai

# Check diff
argocd app diff agentic-ai
```

**Problem:** Flux not reconciling
```bash
# Check Kustomization status
flux get kustomizations

# Force reconciliation
flux reconcile kustomization agentic-ai

# Check logs
flux logs --level=error
```

## Additional Resources

- [Kubernetes Blue/Green Deployments](https://kubernetes.io/blog/2018/04/30/zero-downtime-deployment-kubernetes-jenkins/)
- [Flagger Documentation](https://docs.flagger.app/)
- [ArgoCD Documentation](https://argo-cd.readthedocs.io/)
- [Flux Documentation](https://fluxcd.io/docs/)
- [AWS ECS Blue/Green Deployments](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/deployment-type-bluegreen.html)
- [Argo Rollouts](https://argoproj.github.io/argo-rollouts/)

## Summary

This deployment infrastructure provides production-grade capabilities:

✅ **Zero-downtime deployments** with blue/green strategy
✅ **Progressive rollouts** with canary deployments
✅ **Automated traffic shifting** with Flagger
✅ **GitOps automation** with ArgoCD and Flux
✅ **Continuous monitoring** with auto-rollback
✅ **Infrastructure as Code** with Terraform
✅ **Multi-platform support** (Kubernetes + ECS)

Choose the strategy that best fits your risk tolerance and operational requirements.
