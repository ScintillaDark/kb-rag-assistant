#!/usr/bin/env bash
# Stop the API and UI started by start.sh.
cd "$(dirname "$0")"

for name in api ui; do
  pid_file="logs/${name}.pid"
  if [[ -f "$pid_file" ]]; then
    pid="$(cat "$pid_file")"
    if kill -0 "$pid" 2>/dev/null; then
      kill "$pid" && echo "Stopped ${name} (pid ${pid})"
    fi
    rm -f "$pid_file"
  fi
done
