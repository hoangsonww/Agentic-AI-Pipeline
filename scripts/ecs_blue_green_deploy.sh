#!/usr/bin/env bash
# ECS Blue/Green Deployment via CodeDeploy
# Usage: ./ecs_blue_green_deploy.sh <new-image-tag>

set -euo pipefail

NEW_TAG="${1:-}"
AWS_REGION="${AWS_REGION:-us-east-1}"
APP_NAME="${APP_NAME:-agentic-ai}"
ENV="${ENV:-dev}"

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
ECS Blue/Green Deployment Script

Usage: $0 <image-tag>

Environment Variables:
  AWS_REGION   AWS region (default: us-east-1)
  APP_NAME     Application name (default: agentic-ai)
  ENV          Environment (default: dev)

Example:
  AWS_REGION=us-west-2 APP_NAME=agentic-ai ENV=prod $0 v1.2.0

Prerequisites:
  - AWS CLI configured with appropriate credentials
  - ECS cluster and CodeDeploy resources deployed via Terraform
  - Docker image pushed to ECR with the specified tag

EOF
  exit 1
}

if [[ -z "$NEW_TAG" ]]; then
  usage
fi

# Resolve names
CLUSTER_NAME="${APP_NAME}-${ENV}"
SERVICE_NAME="${APP_NAME}-${ENV}"
CODEDEPLOY_APP="${APP_NAME}-${ENV}"
DEPLOYMENT_GROUP="${APP_NAME}-dg-${ENV}"
ECR_REPO="${APP_NAME}-${ENV}"

log_info "Starting ECS Blue/Green deployment"
log_info "  Region: $AWS_REGION"
log_info "  Application: $APP_NAME"
log_info "  Environment: $ENV"
log_info "  New Tag: $NEW_TAG"
log_info "  Cluster: $CLUSTER_NAME"

# Step 1: Get ECR repository URI
log_info "Step 1: Fetching ECR repository URI..."
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_URI="${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO}"
log_success "ECR URI: $ECR_URI"

# Step 2: Get current task definition
log_info "Step 2: Fetching current task definition..."
TASK_FAMILY="${APP_NAME}-${ENV}"
TASK_DEF_ARN=$(aws ecs describe-services \
  --cluster "$CLUSTER_NAME" \
  --services "$SERVICE_NAME" \
  --region "$AWS_REGION" \
  --query 'services[0].taskDefinition' \
  --output text)

TASK_DEF=$(aws ecs describe-task-definition \
  --task-definition "$TASK_DEF_ARN" \
  --region "$AWS_REGION" \
  --query 'taskDefinition')

# Step 3: Update task definition with new image
log_info "Step 3: Creating new task definition with image ${ECR_URI}:${NEW_TAG}..."

NEW_TASK_DEF=$(echo "$TASK_DEF" | jq --arg img "${ECR_URI}:${NEW_TAG}" \
  '.containerDefinitions[0].image = $img |
   del(.taskDefinitionArn, .revision, .status, .requiresAttributes, .compatibilities, .registeredAt, .registeredBy)')

REGISTERED_TASK=$(aws ecs register-task-definition \
  --region "$AWS_REGION" \
  --cli-input-json "$NEW_TASK_DEF")

NEW_REVISION=$(echo "$REGISTERED_TASK" | jq -r '.taskDefinition.revision')
log_success "Registered new task definition revision: $NEW_REVISION"

# Step 4: Create AppSpec for CodeDeploy
log_info "Step 4: Creating AppSpec for CodeDeploy..."

cat > /tmp/appspec.json <<EOF
{
  "version": 1,
  "Resources": [
    {
      "TargetService": {
        "Type": "AWS::ECS::Service",
        "Properties": {
          "TaskDefinition": "arn:aws:ecs:${AWS_REGION}:${ACCOUNT_ID}:task-definition/${TASK_FAMILY}:${NEW_REVISION}",
          "LoadBalancerInfo": {
            "ContainerName": "app",
            "ContainerPort": 8000
          }
        }
      }
    }
  ]
}
EOF

# Step 5: Create deployment via CodeDeploy
log_info "Step 5: Triggering CodeDeploy Blue/Green deployment..."

DEPLOYMENT_ID=$(aws deploy create-deployment \
  --application-name "$CODEDEPLOY_APP" \
  --deployment-group-name "$DEPLOYMENT_GROUP" \
  --revision "{\"revisionType\":\"AppSpecContent\",\"appSpecContent\":{\"content\":\"$(cat /tmp/appspec.json | jq -c .)\"}}" \
  --region "$AWS_REGION" \
  --query 'deploymentId' \
  --output text)

log_success "Deployment created: $DEPLOYMENT_ID"

# Step 6: Monitor deployment status
log_info "Step 6: Monitoring deployment progress..."

while true; do
  STATUS=$(aws deploy get-deployment \
    --deployment-id "$DEPLOYMENT_ID" \
    --region "$AWS_REGION" \
    --query 'deploymentInfo.status' \
    --output text)

  case "$STATUS" in
    "Succeeded")
      log_success "Deployment succeeded!"
      break
      ;;
    "Failed" | "Stopped")
      log_error "Deployment $STATUS"

      # Get failure details
      ERROR_INFO=$(aws deploy get-deployment \
        --deployment-id "$DEPLOYMENT_ID" \
        --region "$AWS_REGION" \
        --query 'deploymentInfo.errorInformation')

      echo "$ERROR_INFO"
      exit 1
      ;;
    "InProgress" | "Queued" | "Created")
      echo -n "."
      sleep 10
      ;;
    *)
      log_warning "Unknown status: $STATUS"
      sleep 10
      ;;
  esac
done

# Step 7: Verify deployment
log_info "Step 7: Verifying deployment..."

RUNNING_TASKS=$(aws ecs list-tasks \
  --cluster "$CLUSTER_NAME" \
  --service-name "$SERVICE_NAME" \
  --desired-status RUNNING \
  --region "$AWS_REGION" \
  --query 'taskArns' \
  --output json | jq -r '.[]')

TASK_COUNT=$(echo "$RUNNING_TASKS" | wc -l | xargs)
log_success "Running tasks: $TASK_COUNT"

# Get ALB DNS name
ALB_NAME="${APP_NAME}-alb-${ENV}"
ALB_DNS=$(aws elbv2 describe-load-balancers \
  --names "$ALB_NAME" \
  --region "$AWS_REGION" \
  --query 'LoadBalancers[0].DNSName' \
  --output text 2>/dev/null || echo "N/A")

cat <<EOF

${GREEN}Deployment Summary:${NC}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Deployment ID:       $DEPLOYMENT_ID
  New Task Revision:   $NEW_REVISION
  Image:               ${ECR_URI}:${NEW_TAG}
  Running Tasks:       $TASK_COUNT
  Load Balancer:       $ALB_DNS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

${YELLOW}Testing:${NC}
  curl http://${ALB_DNS}/api/new_chat

${YELLOW}Monitoring:${NC}
  aws deploy get-deployment --deployment-id $DEPLOYMENT_ID --region $AWS_REGION

${YELLOW}Rollback:${NC}
  aws deploy stop-deployment --deployment-id $DEPLOYMENT_ID --auto-rollback-enabled --region $AWS_REGION

EOF

rm -f /tmp/appspec.json
