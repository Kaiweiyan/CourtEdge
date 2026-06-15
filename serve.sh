#!/usr/bin/env bash
# Serve the CourtEdge dashboard on a remote workstation (binds all interfaces).
#   bash serve.sh [PORT]
# Then open http://<workstation-ip>:<PORT>  (make sure the port is reachable;
# otherwise tunnel from your laptop:  ssh -L 8501:localhost:8501 user@workstation)
set -euo pipefail
PORT="${1:-8501}"
exec streamlit run app/dashboard.py \
  --server.address 0.0.0.0 \
  --server.port "$PORT" \
  --server.headless true
