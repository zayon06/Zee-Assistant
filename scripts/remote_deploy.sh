#!/bin/bash

# Zee AI v2 — Remote Docker Deployment Helper
# This script helps sync your local docker configuration to a remote server.

if [ -z "$1" ]; then
    echo "Usage: ./scripts/remote_deploy.sh <REMOTE_USER>@<REMOTE_IP>"
    echo "Example: ./scripts/remote_deploy.sh root@1.2.3.4"
    exit 1
fi

REMOTE=$1
DEST="/root/zee-ai"

echo "--- Preparing remote directory: $DEST ---"
ssh $REMOTE "mkdir -p $DEST/searxng"

echo "--- Uploading Docker configurations ---"
scp docker/docker-compose.yml $REMOTE:$DEST/
scp docker/searxng/settings.yml $REMOTE:$DEST/searxng/

echo "--- Starting Containers on Remote Server ---"
ssh $REMOTE "cd $DEST && docker compose pull && docker compose up -d"

echo "--- Deployment Complete ---"
echo "Ollama is now starting and pulling qwen2-vl (this may take a few minutes)."
echo "Update your local .env to use OLLAMA_HOST=http://${REMOTE#*@}:11434"
