#!/usr/bin/env bash
set -euo pipefail
NS="${NS:-default}"
kubectl apply -n "$NS" -f k8s/deployment.yaml
kubectl apply -n "$NS" -f k8s/service.yaml
kubectl apply -n "$NS" -f k8s/ingress.yaml
kubectl rollout status -n "$NS" deploy/agentic-ai
kubectl get svc,deploy,ingress -n "$NS" -l app=agentic-ai
