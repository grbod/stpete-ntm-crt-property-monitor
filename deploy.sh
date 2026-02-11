#!/bin/bash
# Deployment script for stpete-ntm-crt-property-monitor
# Target: Debian 12 VPS on Vultr
# Usage: scp this script to your VPS and run: bash deploy.sh

set -e

APP_DIR="/opt/stpete-monitor"
REPO="https://github.com/grbod/stpete-ntm-crt-property-monitor.git"
USER="monitor"

echo "=== St Pete Property Monitor - VPS Deployment ==="

# 1. System updates and dependencies
echo "[1/7] Installing system packages..."
apt-get update -qq
apt-get install -y -qq python3 python3-venv python3-pip git

# 2. Create service user (no login shell)
echo "[2/7] Creating service user..."
if ! id "$USER" &>/dev/null; then
    useradd -r -s /usr/sbin/nologin -m -d /home/$USER $USER
fi

# 3. Clone repo
echo "[3/7] Cloning repository..."
if [ -d "$APP_DIR" ]; then
    echo "  $APP_DIR exists, pulling latest..."
    cd "$APP_DIR"
    git pull
else
    git clone "$REPO" "$APP_DIR"
    cd "$APP_DIR"
fi

# 4. Set up Python venv and install dependencies
echo "[4/7] Setting up Python environment..."
python3 -m venv "$APP_DIR/venv"
"$APP_DIR/venv/bin/pip" install --quiet --upgrade pip
"$APP_DIR/venv/bin/pip" install --quiet -r "$APP_DIR/requirements.txt"

# 5. Prompt for .env if it doesn't exist
echo "[5/7] Checking .env file..."
if [ ! -f "$APP_DIR/.env" ]; then
    echo ""
    echo "  No .env file found. Creating from template..."
    echo "  You'll need to fill in your credentials."
    echo ""
    cp "$APP_DIR/.env.example" "$APP_DIR/.env"

    read -p "  RAPIDAPI_KEY: " val && sed -i "s|your_rapidapi_key_here|$val|" "$APP_DIR/.env"
    read -p "  SENDGRID_API_KEY: " val && sed -i "s|your_sendgrid_api_key_here|$val|" "$APP_DIR/.env"
    read -p "  SENDER_EMAIL: " val && sed -i "s|your_sender_email@example.com|$val|" "$APP_DIR/.env"
    read -p "  RECIPIENT_EMAIL: " val && sed -i "s|your_recipient_email@example.com|$val|" "$APP_DIR/.env"
    read -p "  RECIPIENT_EMAILS (comma-separated): " val && sed -i "s|email1@example.com,email2@example.com|$val|" "$APP_DIR/.env"
    read -p "  AIRTABLE_BASE_ID: " val && sed -i "s|your_airtable_base_id|$val|" "$APP_DIR/.env"
    read -p "  AIRTABLE_ACCESS_TOKEN: " val && sed -i "s|your_airtable_access_token|$val|" "$APP_DIR/.env"

    echo "  .env created."
else
    echo "  .env already exists, skipping."
fi

# 6. Set ownership and permissions
echo "[6/7] Setting permissions..."
chown -R $USER:$USER "$APP_DIR"
chmod 600 "$APP_DIR/.env"

# 7. Set up cron job (8am ET daily)
echo "[7/7] Setting up cron schedule..."
CRON_FILE="/etc/cron.d/stpete-monitor"
cat > "$CRON_FILE" << 'CRON'
SHELL=/bin/bash
PATH=/usr/local/bin:/usr/bin:/bin
MAILTO=root

# St Pete Property Monitor - runs daily (ET = UTC-5)
# 8:00 AM ET = 13:00 UTC
0 13 * * * monitor cd /opt/stpete-monitor && /opt/stpete-monitor/venv/bin/python /opt/stpete-monitor/main.py >> /opt/stpete-monitor/cron.log 2>&1
CRON
chmod 644 "$CRON_FILE"

echo ""
echo "=== Deployment complete ==="
echo ""
echo "  App directory:  $APP_DIR"
echo "  Python venv:    $APP_DIR/venv"
echo "  Cron schedule:  8:00 AM ET daily"
echo "  Cron log:       $APP_DIR/cron.log"
echo "  App log:        $APP_DIR/property_matches.log"
echo ""
echo "  Test run:  sudo -u monitor $APP_DIR/venv/bin/python $APP_DIR/main.py"
echo "  View logs: tail -f $APP_DIR/property_matches.log"
echo "  Edit cron: nano /etc/cron.d/stpete-monitor"
echo "  Edit .env: nano $APP_DIR/.env"
