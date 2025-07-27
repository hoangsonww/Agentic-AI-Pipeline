#!/usr/bin/env bash
set -euo pipefail
ansible-galaxy install -r requirements.yml
ansible-playbook -i inventories/dev/hosts.ini playbooks/docker.yml
