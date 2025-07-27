#!/bin/bash

# Stop and remove any existing container named "letta-ade-server" to avoid conflicts.
echo "Stopping and removing existing Letta ADE server container if it exists..."
docker stop letta-ade-server > /dev/null 2>&1
docker rm letta-ade-server > /dev/null 2>&1

# Get the absolute path to the directory where this script is located.
# This assumes you place the script in your project's root folder.
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Starting Letta ADE server..."
echo "Mounting project directory: $PROJECT_DIR"

# Run the Letta Docker container with the necessary configurations.
docker run \
  --name letta-ade-server \
  -d \
  -v "$PROJECT_DIR":/app/spds_project \
  -e TOOL_EXEC_DIR="/app/spds_project" \
  -e TOOL_EXEC_VENV_NAME="spds-env" \
  -v ~/.letta/.persist/pgdata:/var/lib/postgresql/data \
  -p 8283:8283 \
  letta/letta:latest

echo "Letta ADE server started successfully."
echo "You can view logs with: docker logs -f letta-ade-server"
echo "To stop the server, run: docker stop letta-ade-server"