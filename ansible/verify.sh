#!/usr/bin/env bash
set -euo pipefail
ansible-playbook -i inventories/dev/hosts.ini playbooks/verify.yml
