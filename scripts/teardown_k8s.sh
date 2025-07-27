#!/usr/bin/env bash
set -euo pipefail
NS="${NS:-default}"
kubectl delete -n "$NS" -f k8s/ingress.yaml --ignore-not-found
kubectl delete -n "$NS" -f k8s/service.yaml --ignore-not-found
kubectl delete -n "$NS" -f k8s/deployment.yaml --ignore-not-found
