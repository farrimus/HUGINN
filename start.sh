#!/bin/bash
cd /opt/eve-frontier
source .venv/bin/activate
# Temporarily disabled SSL for in-game browser compatibility
# To re-enable: add --ssl-keyfile=/opt/eve-frontier/key.pem --ssl-certfile=/opt/eve-frontier/cert.pem
exec uvicorn main:app --host 0.0.0.0 --port 8745
