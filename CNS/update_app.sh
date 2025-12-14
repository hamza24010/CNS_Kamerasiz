#!/bin/bash
set -e

# Log file
LOGfile="/tmp/cns_update.log"
exec > >(tee -a "$LOGfile") 2>&1

echo "Starting update process at $(date)..."

# Target Directory
REPO_DIR="/opt/CNS/repo"
INSTALL_DIR="/opt/CNS"

if [ ! -d "$REPO_DIR/.git" ]; then
    echo "Error: Git repository not found in $REPO_DIR"
    exit 1
fi

cd "$REPO_DIR"

echo "Fetching latest changes..."
git fetch origin

# Determine current branch
BRANCH=$(git rev-parse --abbrev-ref HEAD)
echo "Current branch: $BRANCH"

# Check if there are updates
LOCAL=$(git rev-parse @)
REMOTE=$(git rev-parse "origin/$BRANCH")

if [ "$LOCAL" = "$REMOTE" ]; then
    echo "Already up to date."
    # Optional: Force rebuild anyway if flag passed?
    # For now, just rebuild to be safe or exit?
    # User might want to "Repair". Let's rebuild.
    echo "Rebuilding to ensure consistency..."
else
    echo "New version available. Updating..."
    # Force reset to remote branch state, avoiding merge conflicts
    git reset --hard "origin/$BRANCH"
    git clean -fd
fi

echo "Running build script..."
# Ensure build script is executable
chmod +x CNS/build.sh
cd CNS
./build.sh

echo "Deploying new binary..."
if [ -f "dist/CNS_App" ]; then
    # Handle "Text file busy" by moving the old binary aside first, or writing to a temp file then moving
    # Best practice for updating running binary:
    # 1. Copy new binary to temp name
    cp "dist/CNS_App" "$INSTALL_DIR/CNS_App.new"
    chmod 700 "$INSTALL_DIR/CNS_App.new"

    # 2. Move new over old (atomic replacement)
    mv "$INSTALL_DIR/CNS_App.new" "$INSTALL_DIR/CNS_App"

    echo "Update successful!"
else
    echo "Error: Build failed, binary not found."
    exit 1
fi

echo "Update process finished at $(date)."
