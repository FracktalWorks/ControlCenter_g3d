#!/bin/bash
# =============================================================================
# hostapd-channel-setup.sh
# Detects the channel of the configured STA SSID and writes it to
# /etc/hostapd/hostapd.conf before hostapd starts.
# Falls back to FALLBACK_CHANNEL if the network is not in range.
# =============================================================================
set -euo pipefail

HOSTAPD_CONF="/etc/hostapd/hostapd.conf"
WPA_CONF="/etc/wpa_supplicant/wpa_supplicant.conf"
FALLBACK_CHANNEL=7
LOG_TAG="hostapd-channel-setup"

log() { logger -t "$LOG_TAG" "$*" ; echo "$*" ; }

# Extract SSID from wpa_supplicant.conf
TARGET_SSID=$(grep -oP '(?<=ssid=")[^"]+' "$WPA_CONF" | head -1 || true)
if [ -z "$TARGET_SSID" ]; then
    log "No STA SSID configured in wpa_supplicant.conf; using fallback channel ${FALLBACK_CHANNEL}"
    CHANNEL=$FALLBACK_CHANNEL
else
    log "Looking for SSID: ${TARGET_SSID}"

    # Bring wlan0 up for scanning (non-destructive if already up)
    ip link set wlan0 up 2>/dev/null || true
    sleep 3

    # Scan — may take several seconds
    SCAN_OUTPUT=$(iwlist wlan0 scan 2>/dev/null || true)

    CHANNEL=""
    # Parse scan output: find the cell matching TARGET_SSID, extract its channel
    while IFS= read -r line; do
        if [[ "$line" =~ Channel:([0-9]+) ]]; then
            CURRENT_CH="${BASH_REMATCH[1]}"
        fi
        if [[ "$line" =~ ESSID:\"(.+)\" ]]; then
            if [[ "${BASH_REMATCH[1]}" == "$TARGET_SSID" ]]; then
                CHANNEL="$CURRENT_CH"
                break
            fi
        fi
    done <<< "$SCAN_OUTPUT"

    if [ -z "$CHANNEL" ]; then
        log "SSID '${TARGET_SSID}' not found in scan; using fallback channel ${FALLBACK_CHANNEL}"
        CHANNEL=$FALLBACK_CHANNEL
    else
        log "Found '${TARGET_SSID}' on channel ${CHANNEL}"
    fi
fi

# Update channel= line in hostapd.conf
sed -i "s/^channel=.*/channel=${CHANNEL}/" "$HOSTAPD_CONF"
log "hostapd.conf updated: channel=${CHANNEL}"
