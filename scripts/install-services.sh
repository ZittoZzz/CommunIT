#!/usr/bin/env bash
set -euo pipefail
project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
unit_dir="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
mkdir -p "$unit_dir" "$project_dir/data"
if [[ ! -x "$project_dir/.venv/bin/python" || ! -f "$project_dir/frontend/dist/index.html" ]]; then
  echo 'Install Python dependencies and build the frontend first (see README).'
  exit 1
fi
# systemd quoted strings: escape literal percent, quotes and backslashes in paths.
unit_path="${project_dir//\\/\\\\}"
unit_path="${unit_path//\"/\\\"}"
unit_path="${unit_path//%/%%}"
cat > "$unit_dir/ctfinder-ph-web.service" <<EOF
[Unit]
Description=CTF Finder PH local website
After=network.target

[Service]
Type=simple
WorkingDirectory=$unit_path
EnvironmentFile=-$unit_path/.env
ExecStart="$unit_path/.venv/bin/python" -m backend.app
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
EOF
cat > "$unit_dir/ctfinder-ph-collect.service" <<EOF
[Unit]
Description=Collect Philippine CTF announcements
After=network-online.target

[Service]
Type=oneshot
WorkingDirectory=$unit_path
EnvironmentFile=-$unit_path/.env
ExecStart="$unit_path/.venv/bin/python" -m backend.collect --report data/last-collection.json
TimeoutStartSec=15min
EOF
cat > "$unit_dir/ctfinder-ph-collect.timer" <<'EOF'
[Unit]
Description=Check Philippine CTF announcements daily at 06:00 Asia/Manila

[Timer]
OnCalendar=*-*-* 06:00:00 Asia/Manila
Persistent=true
AccuracySec=1min
Unit=ctfinder-ph-collect.service

[Install]
WantedBy=timers.target
EOF
systemd-analyze --user verify "$unit_dir/ctfinder-ph-web.service" "$unit_dir/ctfinder-ph-collect.service" "$unit_dir/ctfinder-ph-collect.timer"
systemctl --user daemon-reload
systemctl --user enable --now ctfinder-ph-web.service ctfinder-ph-collect.timer
systemctl --user list-timers ctfinder-ph-collect.timer --no-pager
