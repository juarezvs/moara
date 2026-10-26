#!/usr/bin/env bash
# Read-only inventory. Never reads application secrets, environment or databases.
set -u
section() { printf '\n### %s\n' "$1"; }
probe() { "$@" 2>&1 || printf 'UNAVAILABLE_OR_DENIED: %s\n' "$1"; }
section identity
date -u +%FT%TZ
probe hostname
probe id
probe cat /etc/os-release
probe uname -r
section cpu_numa
probe lscpu
probe numactl --hardware
section memory_pressure
probe free -h
probe swapon --show
probe cat /proc/pressure/memory
probe uptime
section storage
probe lsblk -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINTS
probe df -hT
probe findmnt -rn -o TARGET,FSTYPE
section services
probe systemctl list-units --type=service --state=running --no-pager
probe systemctl --failed --no-pager
section network
probe ip -brief address
probe ip route show
probe ss -lntup
probe sudo -n ufw status verbose
section versions
probe docker --version
probe docker compose version
probe python3 --version
probe node --version
probe git --version
probe ollama --version
section containers
probe docker info --format '{{json .SecurityOptions}}'
probe docker ps -a --format '{{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}'
probe docker volume ls
probe docker system df
section inference
probe curl --fail --silent --show-error --max-time 5 http://127.0.0.1:11434/api/tags
probe curl --fail --silent --show-error --max-time 5 http://127.0.0.1:8080/health
section existing_paths
for base in /opt /srv /var/www /home/nutec; do
  if [ -d "$base" ]; then
    probe find "$base" -maxdepth 3 -type d \( -iname '*moara*' -o -iname '*ollama*' -o -iname '*llama*' -o -name .git \)
  fi
done
section thermal
probe sensors
section resource_snapshot
probe docker stats --no-stream --format '{{.Name}} {{.CPUPerc}} {{.MemUsage}}'
section installed_models
probe docker exec ai-server-ollama-1 ollama list
section resident_models
probe docker exec ai-server-ollama-1 ollama ps
section source_map
for base in /home/nutec/ai-server/moara/gateway /home/nutec/ai-server/moara/web/src /home/nutec/ai-server/moara/identity; do
  if [ -d "$base" ]; then
    probe find "$base" -maxdepth 2 -type f \( -name '*.py' -o -name '*.ts' -o -name '*.html' -o -name '*.css' -o -name 'manifest*.json' \)
  fi
done
section privilege_capabilities
if sudo -n true 2>/dev/null; then printf 'passwordless_sudo_available\n'; else printf 'passwordless_sudo_unavailable\n'; fi
section user_units
probe systemctl --user show ai-server.service -p ActiveState -p SubState -p Result -p ExecMainStatus -p FragmentPath -p UnitFileState
probe systemctl --user show ai-backup.service -p ActiveState -p SubState -p Result -p ExecMainStatus -p FragmentPath
probe systemctl --user show ai-backup.timer -p ActiveState -p LastTriggerUSec -p NextElapseUSecRealtime
probe systemctl --user list-units --failed --no-pager
probe loginctl show-user nutec -p Linger
section startup_failure_diagnostics
probe journalctl --user -u ai-server.service -n 18 --no-pager -o cat
section backup_failure_diagnostics
probe journalctl --user -u ai-backup.service -n 18 --no-pager -o cat
