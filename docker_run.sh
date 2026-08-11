#!/usr/bin/env bash
cd /usr/src
# The voice management web UI is opt-in: add
# --web-server --web-server-host 0.0.0.0
exec .venv/bin/python3 -m wyoming_piper \
    --uri 'tcp://0.0.0.0:10200' \
    --data-dir /data "$@"
