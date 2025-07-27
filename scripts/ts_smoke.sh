#!/usr/bin/env bash
set -euo pipefail
pushd clients/ts >/dev/null
npm run dev -- "Give me a brief overview of AMR vendors with citations"
popd >/dev/null
