#!/usr/bin/env python3
"""
WiFi Configuration Web App — Fracktal 1M Pi
============================================
Served at fracktal-1m.local/config via HAProxy.
Runs as root (systemd wifi-config.service) on 127.0.0.1:8888.
"""

from flask import Flask, render_template_string, request, redirect, jsonify
import subprocess
import re
import os

app = Flask(__name__)

# ── HTML Template ─────────────────────────────────────────────────────────────
HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Fracktal &mdash; WiFi Config</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: #f0f2f5; color: #1a1a2e; min-height: 100vh;
      display: flex; flex-direction: column; align-items: center;
      padding: 32px 16px;
    }
    .logo { font-size: 1.5rem; font-weight: 700; color: #1565C0; margin-bottom: 24px; }
    .logo span { color: #e53935; }
    .card {
      background: #fff; border-radius: 10px; padding: 28px 32px;
      box-shadow: 0 4px 16px rgba(0,0,0,.08); width: 100%; max-width: 500px;
      margin-bottom: 20px;
    }
    h2 { font-size: 1.1rem; color: #555; margin-bottom: 20px; font-weight: 500; }
    label { display: block; font-size: .83rem; font-weight: 600;
            color: #444; margin-bottom: 5px; margin-top: 14px; }
    input[type=text], input[type=password], select {
      width: 100%; padding: 10px 12px; border: 1.5px solid #ddd;
      border-radius: 6px; font-size: .95rem; transition: border .2s;
    }
    input:focus, select:focus { border-color: #1565C0; outline: none; }
    .btn {
      display: block; width: 100%; padding: 11px; margin-top: 18px;
      border: none; border-radius: 6px; font-size: .95rem; font-weight: 600;
      cursor: pointer; transition: opacity .2s;
    }
    .btn-primary { background: #1565C0; color: #fff; }
    .btn-secondary {
      background: #f5f5f5; color: #333; border: 1.5px solid #ddd;
      margin-top: 10px;
    }
    .btn:hover { opacity: .85; }
    .alert {
      padding: 12px 16px; border-radius: 6px; font-size: .9rem;
      margin-bottom: 16px; border-left: 4px solid;
    }
    .alert-ok  { background: #E8F5E9; color: #1B5E20; border-color: #43A047; }
    .alert-err { background: #FFEBEE; color: #B71C1C; border-color: #e53935; }
    .net-list { margin-top: 14px; border: 1.5px solid #e0e0e0;
                border-radius: 6px; overflow: hidden; }
    .net-item {
      display: flex; justify-content: space-between; align-items: center;
      padding: 10px 14px; cursor: pointer; font-size: .9rem;
      border-bottom: 1px solid #f0f0f0; transition: background .15s;
    }
    .net-item:last-child { border-bottom: none; }
    .net-item:hover { background: #e8f0fe; }
    .sig { font-size: .78rem; color: #888; }
    .spinner { display: none; color: #1565C0; font-size: .88rem; margin-top: 8px; }
    .status-table { width: 100%; border-collapse: collapse; margin-top: 6px; }
    .status-table td { padding: 9px 4px; vertical-align: top; }
    .status-table tr + tr td { border-top: 1px solid #f0f0f0; }
    .st-label { font-size: .82rem; font-weight: 600; color: #555; width: 130px; padding-right: 12px; white-space: nowrap; }
    .st-ip { font-size: .84rem; color: #1565C0; font-family: monospace; display: block; margin-top: 3px; }
    .badge { display: inline-block; font-size: .74rem; font-weight: 600;
             padding: 2px 9px; border-radius: 10px; }
    .badge-ok  { background: #E8F5E9; color: #2E7D32; }
    .badge-wire { background: #E3F2FD; color: #1565C0; }
    .badge-off { background: #FAFAFA; color: #999; border: 1px solid #ddd; }
    hr { border: none; border-top: 1px solid #eee; margin: 18px 0; }
  </style>
</head>
<body>
  <div class="logo">Fracktal<span>Works</span></div>

  <div class="card">
    <h2>&#x1F4F6; WiFi Station (STA) Configuration</h2>

    {% if message %}
    <div class="alert {{ 'alert-ok' if success else 'alert-err' }}">{{ message }}</div>
    {% endif %}

    <form method="POST" action="/config/save">
      <label for="ssid">Network SSID</label>
      <input type="text" id="ssid" name="ssid"
             value="{{ current_ssid or '' }}"
             placeholder="Select from scan below, or type manually" required>

      <label for="password">Password <small style="font-weight:400;color:#888">(leave blank for open networks)</small></label>
      <input type="password" id="password" name="password"
             placeholder="WPA2 password (8–63 chars)">

      <button type="submit" class="btn btn-primary">&#x1F4BE; Save &amp; Connect</button>
    </form>

    <hr>

    <button class="btn btn-secondary" onclick="scanNetworks()">
      &#x1F50D; Scan for Nearby Networks
    </button>
    <div class="spinner" id="spin">Scanning&hellip; (may take 10&ndash;20 s)</div>
    <div id="scan-results"></div>
  </div>

  <div class="card">
    <h2>&#x1F4BB; Network Status</h2>
    <table class="status-table">
      <tr>
        <td class="st-label">WiFi (wlan0)</td>
        <td>
          {% if wifi_ssid %}
            <span class="badge badge-ok">Connected</span>
            &ldquo;{{ wifi_ssid }}&rdquo;
            <span class="st-ip">{{ wifi_ip or 'no IP assigned' }}</span>
          {% else %}
            <span class="badge badge-off">Not connected</span>
          {% endif %}
        </td>
      </tr>
      <tr>
        <td class="st-label">Ethernet (eth0)</td>
        <td>
          {% if eth_ip %}
            <span class="badge badge-wire">Connected</span>
            <span class="st-ip">{{ eth_ip }}</span>
          {% else %}
            <span class="badge badge-off">Not connected</span>
          {% endif %}
        </td>
      </tr>
    </table>
  </div>

  <script>
  async function scanNetworks() {
    const spin    = document.getElementById('spin');
    const results = document.getElementById('scan-results');
    spin.style.display = 'block';
    results.innerHTML  = '';
    try {
      const r = await fetch('/config/scan');
      const data = await r.json();
      if (data.error) throw new Error(data.error);
      if (!data.length) {
        results.innerHTML = '<p style="margin-top:10px;color:#888;font-size:.88rem">No networks found.</p>';
        return;
      }
      let html = '<div class="net-list">';
      data.forEach(n => {
        const bars = n.signal > -60 ? '&#x2588;&#x2588;&#x2588;' :
                     n.signal > -75 ? '&#x2588;&#x2588;&#x2591;' : '&#x2588;&#x2591;&#x2591;';
        const safe = n.ssid.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/'/g,"\\'");
        html += `<div class="net-item" onclick="pick('${safe}')">
          <span>${n.ssid.replace(/&/g,'&amp;').replace(/</g,'&lt;')}</span>
          <span class="sig">${bars} ${n.signal}&nbsp;dBm &middot; Ch&nbsp;${n.channel}</span>
        </div>`;
      });
      html += '</div>';
      results.innerHTML = html;
    } catch(e) {
      results.innerHTML = `<p style="margin-top:10px;color:#c00;font-size:.88rem">Scan failed: ${e.message}</p>`;
    }
    spin.style.display = 'none';
  }

  function pick(ssid) {
    document.getElementById('ssid').value = ssid;
    document.getElementById('password').focus();
  }
  </script>
</body>
</html>"""

# ── Helpers ───────────────────────────────────────────────────────────────────
def get_network_status():
    """Return WiFi SSID, WiFi IP, and Ethernet IP as a dict."""
    status = {"wifi_ssid": None, "wifi_ip": None, "eth_ip": None}
    try:
        status["wifi_ssid"] = subprocess.run(
            ["iwgetid", "wlan0", "-r"], capture_output=True, text=True
        ).stdout.strip() or None
        m = re.search(r"inet (\d+\.\d+\.\d+\.\d+)",
                      subprocess.run(["ip", "addr", "show", "wlan0"],
                                     capture_output=True, text=True).stdout)
        status["wifi_ip"] = m.group(1) if m else None
        m2 = re.search(r"inet (\d+\.\d+\.\d+\.\d+)",
                       subprocess.run(["ip", "addr", "show", "eth0"],
                                      capture_output=True, text=True).stdout)
        status["eth_ip"] = m2.group(1) if m2 else None
    except Exception:
        pass
    return status


# ── Routes ────────────────────────────────────────────────────────────────────
@app.route("/config", methods=["GET"])
@app.route("/config/", methods=["GET"])
def config():
    net = get_network_status()
    return render_template_string(
        HTML,
        message=request.args.get("msg"),
        success=request.args.get("ok") == "1",
        wifi_ssid=net["wifi_ssid"],
        wifi_ip=net["wifi_ip"],
        eth_ip=net["eth_ip"],
        current_ssid=net["wifi_ssid"] or "",
    )


@app.route("/config/scan")
def scan():
    try:
        result = subprocess.run(
            ["iwlist", "wlan0", "scan"],
            capture_output=True, text=True, timeout=30
        )
        networks = []
        for cell in result.stdout.split("Cell ")[1:]:
            ssid_m = re.search(r'ESSID:"([^"]+)"', cell)
            sig_m  = re.search(r"Signal level=(-\d+)", cell)
            ch_m   = re.search(r"Channel:(\d+)", cell)
            if ssid_m:
                networks.append({
                    "ssid":    ssid_m.group(1),
                    "signal":  int(sig_m.group(1)) if sig_m else -100,
                    "channel": ch_m.group(1) if ch_m else "?",
                })
        # deduplicate — keep strongest signal per SSID
        seen: dict = {}
        for n in networks:
            if n["ssid"] not in seen or n["signal"] > seen[n["ssid"]]["signal"]:
                seen[n["ssid"]] = n
        return jsonify(sorted(seen.values(), key=lambda x: x["signal"], reverse=True))
    except subprocess.TimeoutExpired:
        return jsonify({"error": "Scan timed out (30 s)"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/config/save", methods=["POST"])
def save():
    ssid     = (request.form.get("ssid", "") or "").strip()
    password = (request.form.get("password", "") or "").strip()

    # ── Input validation ──────────────────────────────────────────────────────
    if not ssid:
        return redirect("/config?msg=SSID+is+required&ok=0")
    if len(ssid) > 32:
        return redirect("/config?msg=SSID+too+long+(max+32+chars)&ok=0")
    if password and (len(password) < 8 or len(password) > 63):
        return redirect("/config?msg=WPA+password+must+be+8-63+characters&ok=0")
    # Prevent shell injection via forbidden chars in SSID
    if re.search(r'[\\"\x00-\x1f]', ssid):
        return redirect("/config?msg=SSID+contains+invalid+characters&ok=0")

    # ── Escape for wpa_supplicant config ──────────────────────────────────────
    ssid_escaped = ssid.replace('"', '\\"')

    try:
        if password:
            net_block = (
                f'network={{\n'
                f'\tssid="{ssid_escaped}"\n'
                f'\tpsk="{password}"\n'
                f'}}'
            )
        else:
            net_block = (
                f'network={{\n'
                f'\tssid="{ssid_escaped}"\n'
                f'\tkey_mgmt=NONE\n'
                f'}}'
            )

        config_content = (
            "country=IN\n"
            "ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev\n"
            "update_config=1\n\n"
            f"{net_block}\n"
        )

        wpa_conf = "/etc/wpa_supplicant/wpa_supplicant.conf"
        # Backup existing config
        if os.path.exists(wpa_conf):
            with open(wpa_conf, "r") as f:
                backup = f.read()
            with open(wpa_conf + ".bak", "w") as f:
                f.write(backup)

        with open(wpa_conf, "w") as f:
            f.write(config_content)

        # Trigger reconnect (non-blocking)
        subprocess.Popen(
            ["wpa_cli", "-i", "wlan0", "reconfigure"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )

        ssid_safe = ssid.replace(" ", "+")
        return redirect(f"/config?msg=Saved+and+connecting+to+{ssid_safe}&ok=1")

    except OSError as e:
        return redirect(f"/config?msg=File+write+error:+{str(e)}&ok=0")
    except Exception as e:
        return redirect(f"/config?msg=Error:+{str(e)}&ok=0")


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8888, debug=False)
