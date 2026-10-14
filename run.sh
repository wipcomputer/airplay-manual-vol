#!/bin/sh
# Start the web prototype of the panel from a clone of the repo.
# First run sets up Python. Pass --lan to open the setup page from your phone.
set -e
cd "$(dirname "$0")"
if [ ! -x .venv/bin/wallvol ]; then
  python3 -m venv .venv
  .venv/bin/pip install --quiet -e .
fi
# Matter devices (plugs, lights, dimmers) need the Node-based Matter bridge
if [ ! -d wallvol/matter/node_modules ] && command -v npm >/dev/null 2>&1; then
  (cd wallvol/matter && npm install --silent)
fi
exec .venv/bin/wallvol --home . "$@"
