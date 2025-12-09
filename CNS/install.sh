#!/bin/bash
set -e

# Check if running as root
if [ "$EUID" -ne 0 ]; then
  echo "Please run as root (sudo ./install.sh)"
  exit 1
fi

APP_NAME="CNS_App"
INSTALL_DIR="/opt/CNS"
DESKTOP_DIR=$(eval echo ~${SUDO_USER}/Desktop)
ICON_NAME="cns_icon.png"

echo "Installing system dependencies..."
apt-get update
# libatlas-base-dev removed as it caused issues on newer Debian versions. 
# Numpy wheels usually include necessary libraries.
apt-get install -y libgl1 libqt5gui5 libqt5widgets5

echo "Creating installation directory at $INSTALL_DIR..."
mkdir -p "$INSTALL_DIR"

echo "Copying application files..."
# Assuming we are running from the source directory and build.sh has been run
if [ -f "dist/$APP_NAME" ]; then
    cp "dist/$APP_NAME" "$INSTALL_DIR/"
else
    echo "Error: dist/$APP_NAME not found. Did you run build.sh?"
    exit 1
fi

# Copy assets
cp "mainDb.sqlite" "$INSTALL_DIR/" || echo "Warning: mainDb.sqlite not found, skipping."
cp "mainDb1.sqlite" "$INSTALL_DIR/" || echo "Warning: mainDb1.sqlite not found, skipping."
cp "icon.png" "$INSTALL_DIR/$ICON_NAME" || echo "Warning: icon.png not found, skipping."
cp "DejaVuSans.ttf" "$INSTALL_DIR/" || echo "Warning: DejaVuSans.ttf not found, skipping."
cp "settings.py" "$INSTALL_DIR/" || echo "Warning: settings.py not found, skipping."

# Set permissions (Strictly Root Only)
echo "Setting permissions..."
chown -R root:root "$INSTALL_DIR"
chmod -R 700 "$INSTALL_DIR"

# Configure sudoers for passwordless execution
echo "Configuring passwordless sudo for $APP_NAME..."
SUDOERS_FILE="/etc/sudoers.d/cns_app"
echo "$SUDO_USER ALL=(root) NOPASSWD: $INSTALL_DIR/$APP_NAME" > "$SUDOERS_FILE"
chmod 0440 "$SUDOERS_FILE"

# Create Desktop Shortcut
echo "Creating Desktop shortcut..."
# Create debug log with open permissions
touch /tmp/cns_debug.log
chmod 666 /tmp/cns_debug.log

cat > "$DESKTOP_DIR/$APP_NAME.desktop" << EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=CNS Control
Comment=CNS Control Application
Exec=sudo $INSTALL_DIR/$APP_NAME
Icon=$INSTALL_DIR/$ICON_NAME
Terminal=false
StartupNotify=true
Categories=Utility;
EOF

# Fix shortcut permissions
chown $SUDO_USER:$SUDO_USER "$DESKTOP_DIR/$APP_NAME.desktop"
chmod +x "$DESKTOP_DIR/$APP_NAME.desktop"

# Also install to system menu
cp "$DESKTOP_DIR/$APP_NAME.desktop" "/usr/share/applications/"

# Attempt to disable "Execute File" prompt in PCManFM/LibFM
# This sets quick_exec=1 in the user's config
USER_HOME=$(eval echo ~${SUDO_USER})
LIBFM_CONF="$USER_HOME/.config/libfm/libfm.conf"

if [ -f "$LIBFM_CONF" ]; then
    echo "Configuring file manager to skip execution prompt..."
    # Check if [config] section exists, if not add it (rare)
    if ! grep -q "\[config\]" "$LIBFM_CONF"; then
        echo "[config]" >> "$LIBFM_CONF"
    fi
    
    # Set quick_exec=1
    if grep -q "quick_exec=" "$LIBFM_CONF"; then
        sed -i 's/quick_exec=0/quick_exec=1/g' "$LIBFM_CONF"
    else
        sed -i '/\[config\]/a quick_exec=1' "$LIBFM_CONF"
    fi
    chown $SUDO_USER:$SUDO_USER "$LIBFM_CONF"
fi

echo "Installation Complete!"
echo "The application is installed in $INSTALL_DIR"
echo "Only the root user can access this directory."
echo "You can launch the application from the Desktop shortcut (Password required)."
