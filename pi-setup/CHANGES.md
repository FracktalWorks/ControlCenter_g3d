# Fracktal 1M Pi — Configuration Changes Log

**Date:** 2026-05-28  
**Pi IP (eth0):** 192.168.1.30  
**Pi User:** pi  
**Performed by:** automated setup via `fracktal-setup.sh`

---

## Pre-Change Audit (snapshot before any changes)

| Item | Before | After |
|------|--------|-------|
| OS | Raspbian GNU/Linux 10 (Buster) | same |
| Kernel | 5.10.103-v7l+ (ARMv7) | same |
| Hostname | `raspberrypi` | `fracktal-1m` |
| mDNS name | `raspberrypi.local` | `fracktal-1m.local` |
| wlan0 | DOWN (wpa_supplicant active, no carrier) | AP+STA concurrent mode |
| uap0 | did not exist | virtual AP interface (192.168.50.1) |
| hostapd | not installed | installed, AP on `uap0` |
| dnsmasq | not installed | installed, DHCP on 192.168.50.0/24 |
| WiFi config page | none | `fracktal-custom.local/config` |
| HAProxy `/config` route | not configured | → Flask on 127.0.0.1:8888 |
| python3-flask | not installed | installed |
| OctoPrint | `raspberrypi.local` port 80 | **unchanged** at `fracktal-custom.local` port 80 |

---

## Change 1 — apt Sources (Raspbian Buster EOL)

**Problem:** `http://raspbian.raspberrypi.org/raspbian buster` returned HTTP 404 (repository decommissioned).

**Fix applied to `/etc/apt/sources.list`:**
```
# OLD (dead):
deb http://raspbian.raspberrypi.org/raspbian/ buster main contrib non-free rpi

# NEW (archive):
deb [trusted=yes] http://archive.debian.org/debian/ buster main contrib non-free
```

**New file `/etc/apt/sources.list.d/buster-security.list`:**
```
deb [trusted=yes] http://archive.debian.org/debian-security buster/updates main contrib non-free
```

**New file `/etc/apt/apt.conf.d/99no-check-valid`:**
```
Acquire::Check-Valid-Until "false";
```
> Required because the archive's Release file has expired dates (EOL archive behaviour).

---

## Change 2 — Hostname

**Files modified:**
- `/etc/hostname` — `raspberrypi` → `fracktal-custom`
- `/etc/hosts` — updated `127.0.1.1` entry to `fracktal-custom`

**Note:** Linux hostnames cannot contain underscores (RFC 952). The user requested `fracktal_custom.local` but the valid equivalent is `fracktal-custom.local`.

mDNS advertisement via `avahi-daemon` (already installed) will advertise `fracktal-custom.local` automatically once hostname is set.

**Backup:** saved to `/home/pi/config_backups_<timestamp>/hostname` and `hosts`

---

## Change 3 — Packages Installed

```
hostapd      — WiFi Access Point daemon
dnsmasq      — Lightweight DHCP + DNS server (used for AP clients)
python3-flask — Web framework for the WiFi config page
```

---

## Change 4 — AP+STA Concurrent Mode

### How it works
The Broadcom BCM43xx chip (brcmfmac driver) supports running one AP interface and one STA interface simultaneously, but both must be on the **same 2.4 GHz channel** (`#channels <= 1` constraint).

### Virtual interface `uap0`
A virtual AP interface (`uap0`) is created from the physical `wlan0` radio using:
```bash
iw dev wlan0 interface add uap0 type __ap
```
- `wlan0` → STA mode, managed by `wpa_supplicant` (connects to "Fracktal Works 2.4")
- `uap0` → AP mode, managed by `hostapd` (broadcasts "Fracktal_1M_Setup")

### New systemd service: `/etc/systemd/system/uap0-iface.service`
Creates the `uap0` virtual interface at boot, before `hostapd` and `dnsmasq` start.

### New systemd service: `/etc/systemd/system/hostapd-channel-setup.service`
Script at `/usr/local/bin/hostapd-channel-setup.sh`:
- Scans for the STA target SSID at boot
- If found: sets hostapd channel to match (ensures AP+STA work on the same channel)
- If not found: uses default **channel 7** (fallback)

### hostapd config: `/etc/hostapd/hostapd.conf`
```
interface=uap0
ssid=Fracktal_1M_Setup
hw_mode=g
channel=7           ← updated dynamically by hostapd-channel-setup.sh
wpa=2
wpa_passphrase=Fracktal1234
```

### AP network
| Item | Value |
|------|-------|
| SSID | `Fracktal_1M_Setup` |
| Password | `Fracktal1234` |
| AP IP | `192.168.50.1` |
| DHCP range | `192.168.50.10 – 192.168.50.100` |
| Channel | Auto-detected (default 7) |

---

## Change 5 — dnsmasq config: `/etc/dnsmasq.conf`

```
interface=uap0
no-dhcp-interface=lo,eth0,wlan0
bind-interfaces
server=8.8.8.8
dhcp-range=192.168.50.10,192.168.50.100,255.255.255.0,12h
dhcp-option=3,192.168.50.1
```
> Only serves DHCP on the AP interface. eth0 and wlan0 remain managed by dhcpcd.

---

## Change 6 — dhcpcd: `/etc/dhcpcd.conf` (appended)

```
interface uap0
    static ip_address=192.168.50.1/24
    nohook wpa_supplicant
```

---

## Change 7 — WiFi Config Web App

**Deployed to:** `/opt/wifi-config/app.py`  
**Listens on:** `127.0.0.1:8888` (localhost only — exposed via HAProxy)  
**Runs as:** `root` (required to write `/etc/wpa_supplicant/wpa_supplicant.conf`)

**New systemd service:** `/etc/systemd/system/wifi-config.service`

### Features
- `GET  /config`      — Config page (WiFi network selection form)
- `GET  /config/scan` — JSON API: scan visible WiFi networks (`iwlist wlan0 scan`)
- `POST /config/save` — Validates & saves new SSID/password to `wpa_supplicant.conf`, triggers `wpa_cli reconfigure`

### Security
- HTTP Basic Auth required (default: `admin` / `fracktal`)
- SSID input validated: max 32 chars, no control characters, no backslash/quote injection
- WPA password validated: 8–63 characters
- Input sanitization via Python regex before writing to config file
- Old `wpa_supplicant.conf` backed up to `.bak` before each save

---

## Change 8 — HAProxy: `/etc/haproxy/haproxy.cfg`

Added `wificonfig` backend and route. **OctoPrint is unaffected.**

```
frontend public
    bind :::80 v4v6
    use_backend wificonfig if { path_beg /config }   ← NEW
    use_backend webcam     if { path_beg /webcam/ }
    default_backend octoprint                        ← OctoPrint unchanged

backend wificonfig                                   ← NEW
    option forwardfor
    server wificonfig1 127.0.0.1:8888
```

**Backup:** saved to `/home/pi/config_backups_<timestamp>/haproxy.cfg`

---

## Change 9 — IP Forwarding

`/etc/sysctl.conf`: uncommented `net.ipv4.ip_forward=1`  
Enables routing between `uap0` (AP clients) and `eth0`/`wlan0` (internet).

---

## Change 10 — dnsmasq Startup Fix (post-reboot issue)

**Problem discovered on first reboot:** dnsmasq started before the `uap0` virtual interface was created, causing it to fail with `unknown interface uap0`.

**Root cause:** `bind-interfaces` in `/etc/dnsmasq.conf` requires the interface to already exist at startup.

**Fix 1 — `/etc/dnsmasq.conf`:** Changed `bind-interfaces` → `bind-dynamic`
- `bind-dynamic` attaches to interfaces as they appear; tolerates uap0 being created after dnsmasq starts.

**Fix 2 — `/etc/systemd/system/dnsmasq.service.d/wait-uap0.conf`** (new file):
```ini
[Unit]
After=uap0-iface.service
Wants=uap0-iface.service
```
- Ensures proper ordering: dnsmasq starts after uap0 is created, even if systemd parallelises startup.

Both fixes are incorporated into `fracktal-setup.sh` (idempotent, safe to re-run).

---

## Service Startup Order (boot sequence)

```
sys-subsystem-net-devices-wlan0.device
    └── uap0-iface.service          (creates uap0 virtual interface)
            ├── hostapd-channel-setup.service  (detects STA channel, updates hostapd.conf)
            │       └── hostapd.service         (starts AP on uap0)
            └── dnsmasq.service         (starts DHCP for AP clients — After=uap0-iface)
network.target
    └── wifi-config.service         (Flask app on 127.0.0.1:8888)
```

---

## Change 11 — Hostname Renamed to fracktal-1m

`/etc/hostname` changed from `fracktal-custom` → `fracktal-1m`.  
`/etc/hosts` updated accordingly. mDNS address is now `fracktal-1m.local`.

---

## Change 12 — OctoPrint reverseProxy Config

Added `server.reverseProxy` section to `~/.octoprint/config.yaml`:
```yaml
server:
  reverseProxy:
    trustedDownstream:
    - 127.0.0.1
    hostHeader: X-Forwarded-Host
    schemeHeader: X-Forwarded-Proto
    schemeFallback: http
    hostFallback: fracktal-1m.local
```
Also added `http-request set-header X-Forwarded-Host %[req.hdr(host)]` to the HAProxy frontend so OctoPrint receives the original hostname. This ensures:
- OctoPrint generates session cookies scoped to the correct hostname (`fracktal-1m.local`)
- Auto-login (`autologinLocal: true`) works correctly when accessing via `fracktal-1m.local`
- OctoPrint name updated to `Fracktal 1M` in `appearance.name`

**Note on auto-login behaviour:** OctoPrint auto-login works by setting a session cookie on the **first** page load. If your browser has a pre-existing session cookie for the IP (`192.168.1.30`), it auto-logs in instantly via the IP. For `fracktal-1m.local`, the first visit will auto-log you in and set a cookie for that domain — no credentials needed.

---

## Change 13 — Removed Basic Auth from /config WiFi Page

The Flask WiFi config app (`/opt/wifi-config/app.py`) previously required HTTP Basic Auth (`admin` / `fracktal`) to access `/config`.

**Removed:** `@auth_required` decorator from all three routes (`/config`, `/config/scan`, `/config/save`) and the entire `auth_required` / `check_auth` helper block.

`/config` is now open access — no browser login popup.

---

## Access Points After Reboot

| URL | Service | Notes |
|-----|---------|-------|
| `fracktal-1m.local` | OctoPrint | Auto-login as `admin` |
| `fracktal-1m.local/config` | WiFi Config | Open access, no login required |
| `192.168.1.30` | OctoPrint (eth0) | Direct IP always works |
| `192.168.50.1/config` | WiFi Config (AP) | When connected to `Fracktal_1M_Setup` AP |

---

## Backup Location on Pi

All original config files backed up to: `/home/pi/config_backups_<timestamp>/`

Files backed up:
- `hostname`
- `hosts`
- `dhcpcd.conf`
- `haproxy.cfg`
- `wpa_supplicant.conf`
- `dnsmasq.conf`

---

## Known Constraints

1. **Single channel AP+STA:** The BCM43xx chip forces both interfaces to the same 2.4 GHz channel. If the home router ("Fracktal Works 2.4") is not on the auto-detected channel, STA may not connect. The AP (`Fracktal_1M_Setup`) will always work regardless.

2. **Raspbian Buster is EOL:** System should be upgraded to Raspbian Bullseye (11) or Bookworm (12) when possible. The apt archive workaround (`[trusted=yes]`) is a temporary measure.

3. **No HTTPS on config page:** The `/config` page uses HTTP. On the local AP network (192.168.50.0/24) this is acceptable. Do not expose port 80 to the internet.

4. **Change default credentials** after first use:
   - AP password: edit `/etc/hostapd/hostapd.conf` → `wpa_passphrase=`
   - Config page auth: edit `/opt/wifi-config/app.py` → `AUTH_PASS =`
   - Run `sudo systemctl restart hostapd` / `sudo systemctl restart wifi-config` after changes

---

## Files Created/Modified on Pi

| File | Action |
|------|--------|
| `/etc/hostname` | Modified |
| `/etc/hosts` | Modified |
| `/etc/apt/sources.list` | Modified (EOL fix) |
| `/etc/apt/sources.list.d/buster-security.list` | Created |
| `/etc/apt/apt.conf.d/99no-check-valid` | Created |
| `/etc/hostapd/hostapd.conf` | Created |
| `/etc/default/hostapd` | Modified (DAEMON_CONF path) |
| `/etc/dnsmasq.conf` | Replaced |
| `/etc/dhcpcd.conf` | Appended |
| `/etc/sysctl.conf` | Modified (ip_forward) |
| `/etc/haproxy/haproxy.cfg` | Replaced |
| `/etc/systemd/system/uap0-iface.service` | Created |
| `/etc/systemd/system/hostapd-channel-setup.service` | Created |
| `/etc/systemd/system/wifi-config.service` | Created |
| `/usr/local/bin/hostapd-channel-setup.sh` | Created |
| `/opt/wifi-config/app.py` | Created |

---

## Files in This Repository (`pi-setup/`)

| File | Purpose |
|------|---------|
| `fracktal-setup.sh` | Master setup script (idempotent, run as root) |
| `wifi-config-app.py` | Flask WiFi config web app |
| `hostapd-channel-setup.sh` | Boot-time channel auto-detection script |
| `CHANGES.md` | This file |
