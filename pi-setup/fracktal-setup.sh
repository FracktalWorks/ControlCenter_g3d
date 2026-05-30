#!/bin/bash
# =============================================================================
# fracktal-setup.sh  —  Master setup script
# Run as root on the Raspberry Pi.
# =============================================================================
# What this script does (in order):
#   1. Backs up all configs it will modify
#   2. Changes hostname to fracktal_custom
#   3. Installs hostapd, dnsmasq, python3-flask
#   4. Creates hostapd config (AP: SSID=Fracktal_1M_Setup)
#   5. Creates dnsmasq config (DHCP on 192.168.50.0/24)
#   6. Adds static IP for uap0 in dhcpcd.conf
#   7. Creates uap0 virtual-interface systemd service
#   8. Creates hostapd-channel-setup systemd service
#   9. Deploys WiFi-config Flask app to /opt/wifi-config/
#  10. Creates wifi-config systemd service
#  11. Updates HAProxy to route /config → Flask (port 8888)
#  12. Enables IP forwarding
#  13. Enables all new services
#  14. Prints reboot prompt
# =============================================================================
set -euo pipefail
LOGFILE="/home/pi/fracktal_setup_$(date +%Y%m%d_%H%M%S).log"
exec > >(tee -a "$LOGFILE") 2>&1
echo "====== Fracktal Custom Pi Setup — $(date) ======"

BACKUP_DIR="/home/pi/config_backups_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"
echo "[BACKUP] Saving originals to $BACKUP_DIR"
cp /etc/hostname              "$BACKUP_DIR/hostname"             2>/dev/null || true
cp /etc/hosts                 "$BACKUP_DIR/hosts"                2>/dev/null || true
cp /etc/dhcpcd.conf           "$BACKUP_DIR/dhcpcd.conf"          2>/dev/null || true
cp /etc/haproxy/haproxy.cfg   "$BACKUP_DIR/haproxy.cfg"          2>/dev/null || true
cp /etc/wpa_supplicant/wpa_supplicant.conf "$BACKUP_DIR/wpa_supplicant.conf" 2>/dev/null || true

# ── 1. Hostname ───────────────────────────────────────────────────────────────
# Note: Linux hostnames may not contain underscores (RFC 952)
echo "[1/13] Setting hostname to fracktal-1m"
echo 'fracktal-1m' > /etc/hostname
sed -i 's/\braspberrypi\b/fracktal-1m/g' /etc/hosts
# Fix any prior variant
sed -i 's/fracktal-custom/fracktal-1m/g' /etc/hosts
sed -i 's/fracktal_custom/fracktal-1m/g' /etc/hosts
hostname fracktal-1m
systemctl restart avahi-daemon

# ── 2. Fix apt sources (Raspbian Buster is EOL) & install packages ────────────
echo "[2/13] Fixing apt sources for Raspbian Buster EOL, then installing packages"

# Replace dead raspbian.raspberrypi.org with archive.debian.org
cat > /etc/apt/sources.list << 'SRCEOF'
deb [trusted=yes] http://archive.debian.org/debian/ buster main contrib non-free
SRCEOF

# Security archive
cat > /etc/apt/sources.list.d/buster-security.list << 'SRCEOF'
deb [trusted=yes] http://archive.debian.org/debian-security buster/updates main contrib non-free
SRCEOF

# Disable valid-until check (Release file dates are expired for EOL archives)
echo 'Acquire::Check-Valid-Until "false";' > /etc/apt/apt.conf.d/99no-check-valid

apt-get update -q
DEBIAN_FRONTEND=noninteractive apt-get install -y hostapd dnsmasq python3-flask
systemctl unmask hostapd
systemctl disable hostapd   # managed via our ordering
systemctl stop hostapd 2>/dev/null || true
systemctl disable dnsmasq
systemctl stop dnsmasq 2>/dev/null || true

# ── 3. hostapd config ─────────────────────────────────────────────────────────
echo "[3/13] Writing /etc/hostapd/hostapd.conf"
cat > /etc/hostapd/hostapd.conf << 'EOF'
interface=uap0
driver=nl80211
ssid=Fracktal_1M_Setup
hw_mode=g
channel=7
wmm_enabled=0
macaddr_acl=0
auth_algs=1
ignore_broadcast_ssid=0
wpa=2
wpa_passphrase=Fracktal1234
wpa_key_mgmt=WPA-PSK
wpa_pairwise=TKIP
rsn_pairwise=CCMP
EOF

# Point the default hostapd config at our file
sed -i 's|#DAEMON_CONF=""|DAEMON_CONF="/etc/hostapd/hostapd.conf"|g' /etc/default/hostapd
# Also cover the case where it's already set to something else
sed -i 's|^DAEMON_CONF=.*|DAEMON_CONF="/etc/hostapd/hostapd.conf"|g' /etc/default/hostapd

# ── 4. dnsmasq config ─────────────────────────────────────────────────────────
echo "[4/13] Writing /etc/dnsmasq.conf"
cp /etc/dnsmasq.conf "$BACKUP_DIR/dnsmasq.conf" 2>/dev/null || true
cat > /etc/dnsmasq.conf << 'EOF'
# Fracktal Custom Pi — dnsmasq config
# Provides DHCP only on the AP (uap0) interface.
interface=uap0
no-dhcp-interface=lo,eth0,wlan0
# bind-dynamic: tolerates uap0 being created after dnsmasq starts
bind-dynamic
server=8.8.8.8
bogus-priv
dhcp-range=192.168.50.10,192.168.50.100,255.255.255.0,12h
dhcp-option=3,192.168.50.1
EOF

# ── 5. dhcpcd — static IP for uap0 ───────────────────────────────────────────
echo "[5/13] Adding uap0 static IP to /etc/dhcpcd.conf"
if ! grep -q 'interface uap0' /etc/dhcpcd.conf; then
  cat >> /etc/dhcpcd.conf << 'EOF'

# ── Fracktal AP (uap0) — static address ──────────────────────────────────────
interface uap0
    static ip_address=192.168.50.1/24
    nohook wpa_supplicant
EOF
fi

# ── 6. uap0 virtual-interface service ────────────────────────────────────────
echo "[6/13] Creating /etc/systemd/system/uap0-iface.service"
# Derive uap0 MAC: wlan0 MAC with last byte +1
WLAN0_MAC=$(cat /sys/class/net/wlan0/address)
UAP0_LAST=$(printf '%02x' $(( (16#$(echo "$WLAN0_MAC" | awk -F: '{print $6}') + 1) % 256 )))
UAP0_MAC=$(echo "$WLAN0_MAC" | awk -F: -v last="$UAP0_LAST" '{printf "%s:%s:%s:%s:%s:%s",$1,$2,$3,$4,$5,last}')
echo "  wlan0=$WLAN0_MAC  uap0=$UAP0_MAC"

cat > /etc/systemd/system/uap0-iface.service << SVCEOF
[Unit]
Description=Create uap0 virtual WiFi AP interface
After=sys-subsystem-net-devices-wlan0.device
Before=hostapd.service
Before=dnsmasq.service

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/sbin/iw dev wlan0 interface add uap0 type __ap
ExecStart=/bin/ip link set uap0 address ${UAP0_MAC}
ExecStop=/bin/ip link set uap0 down
ExecStop=/sbin/iw dev uap0 del

[Install]
WantedBy=multi-user.target
SVCEOF

# ── 7. hostapd-channel-setup service ─────────────────────────────────────────
echo "[7/13] Installing /usr/local/bin/hostapd-channel-setup.sh"
cp /tmp/hostapd-channel-setup.sh /usr/local/bin/hostapd-channel-setup.sh
chmod +x /usr/local/bin/hostapd-channel-setup.sh

cat > /etc/systemd/system/hostapd-channel-setup.service << 'SVCEOF'
[Unit]
Description=Detect STA WiFi channel and configure hostapd accordingly
After=uap0-iface.service
Before=hostapd.service

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/usr/local/bin/hostapd-channel-setup.sh

[Install]
WantedBy=multi-user.target
SVCEOF

# ── 8. WiFi-config Flask app ──────────────────────────────────────────────────
echo "[8/13] Deploying /opt/wifi-config/app.py"
mkdir -p /opt/wifi-config
cp /tmp/wifi-config-app.py /opt/wifi-config/app.py
chmod 700 /opt/wifi-config/app.py

cat > /etc/systemd/system/wifi-config.service << 'SVCEOF'
[Unit]
Description=Fracktal WiFi Configuration Web App
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/wifi-config
ExecStart=/usr/bin/python3 /opt/wifi-config/app.py
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
SVCEOF

# ── 9. HAProxy — add /config backend ─────────────────────────────────────────
echo "[9/13] Updating /etc/haproxy/haproxy.cfg"
cat > /etc/haproxy/haproxy.cfg << 'EOF'
global
        maxconn 4096
        user haproxy
        group haproxy
        daemon
        log 127.0.0.1 local0 debug

defaults
        log     global
        mode    http
        option  httplog
        option  dontlognull
        retries 3
        option redispatch
        option http-server-close
        option forwardfor
        maxconn 2000
        timeout connect 5s
        timeout client  15min
        timeout server  15min

frontend public
        bind :::80 v4v6
        # WiFi config tool — must come before the catch-all OctoPrint rule
        http-request set-header X-Forwarded-Host %[req.hdr(host)]
        use_backend wificonfig if { path_beg /config }
        use_backend webcam     if { path_beg /webcam/ }
        default_backend octoprint

backend octoprint
        reqrep ^([^\ :]*)\ /(.*)     \1\ /\2
        option forwardfor
        server octoprint1 127.0.0.1:5000

backend webcam
        reqrep ^([^\ :]*)\ /webcam/(.*)     \1\ /\2
        server webcam1 127.0.0.1:8080

backend wificonfig
        option forwardfor
        server wificonfig1 127.0.0.1:8888
EOF

# ── 10. IP forwarding ─────────────────────────────────────────────────────────
echo "[10/13] Enabling IP forwarding"
sed -i 's/#net.ipv4.ip_forward=1/net.ipv4.ip_forward=1/' /etc/sysctl.conf
sysctl -p 2>/dev/null || true

# ── 10b. OctoPrint reverseProxy config ───────────────────────────────────────
echo "[10b/13] Configuring OctoPrint reverseProxy for fracktal-1m.local"
python3 << 'PYEOF'
import yaml
config_path = "/home/pi/.octoprint/config.yaml"
try:
    with open(config_path) as f:
        cfg = yaml.safe_load(f) or {}
except FileNotFoundError:
    cfg = {}
cfg.setdefault("server", {})["reverseProxy"] = {
    "trustedDownstream": ["127.0.0.1"],
    "hostHeader": "X-Forwarded-Host",
    "schemeHeader": "X-Forwarded-Proto",
    "schemeFallback": "http",
    "hostFallback": "fracktal-1m.local",
}
cfg.setdefault("appearance", {})["name"] = "Fracktal 1M"
with open(config_path, "w") as f:
    yaml.dump(cfg, f, default_flow_style=False, allow_unicode=True)
print("OctoPrint config updated")
PYEOF

# ── 11. Enable services ───────────────────────────────────────────────────────
echo "[11/13] Enabling systemd services"
# Systemd drop-in: ensure dnsmasq starts AFTER uap0 is created
mkdir -p /etc/systemd/system/dnsmasq.service.d
cat > /etc/systemd/system/dnsmasq.service.d/wait-uap0.conf << 'DROPIN'
[Unit]
After=uap0-iface.service
Wants=uap0-iface.service
DROPIN
systemctl daemon-reload
systemctl enable uap0-iface.service
systemctl enable hostapd-channel-setup.service
systemctl enable hostapd.service
systemctl enable dnsmasq.service
systemctl enable wifi-config.service

# ── 12. Validate HAProxy config ───────────────────────────────────────────────
echo "[12/13] Validating HAProxy config"
haproxy -c -f /etc/haproxy/haproxy.cfg && echo "  HAProxy config OK" || echo "  WARNING: HAProxy config check failed!"

echo ""
echo "====== Setup complete ======"
echo "Setup log saved to: $LOGFILE"
echo "Config backups at:  $BACKUP_DIR"
echo ""
echo "Changes summary:"
echo "  Hostname    : fracktal-1m  (fracktal-1m.local via mDNS)"
echo "  AP SSID     : Fracktal_1M_Setup (password: Fracktal1234)"
echo "  AP subnet   : 192.168.50.0/24  (Pi at 192.168.50.1)"
echo "  OctoPrint   : fracktal-1m.local  (auto-login enabled)"
echo "  WiFi Config : fracktal-1m.local/config  (open access, no login)"
echo ""
echo "[13/13] Rebooting in 10 seconds ... (Ctrl-C to cancel)"
sleep 10
reboot
