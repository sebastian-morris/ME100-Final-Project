# test_notification.py
# Manually test ntfy.sh push notifications from the ESP32.
#
# How to use:
#   1. Fill in config.py: WIFI_SSID, WIFI_PASSWORD, NTFY_TOPIC
#   2. Install the ntfy app on your phone and subscribe to your NTFY_TOPIC
#   3. Upload this file and config.py to the ESP32, then run this file in Thonny
#   4. Notifications fire automatically every 3 seconds
#   5. Stop the script in Thonny (Stop/Restart button) to end

import time
import network
import urequests
import config

SEND_INTERVAL_MS = 3000   # ms between notifications

# ---------------------------------------------------------------------------
# WiFi
# ---------------------------------------------------------------------------

def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if wlan.isconnected():
        print(f"Already connected — IP: {wlan.ifconfig()[0]}")
        return True

    print(f"Connecting to '{config.WIFI_SSID}' ", end="")
    wlan.connect(config.WIFI_SSID, config.WIFI_PASSWORD)

    for _ in range(20):          # 10-second timeout
        if wlan.isconnected():
            break
        print(".", end="")
        time.sleep_ms(500)
    print()

    if wlan.isconnected():
        print(f"Connected — IP: {wlan.ifconfig()[0]}")
        return True
    else:
        print("ERROR: WiFi connection failed. Check SSID and password in config.py.")
        return False

# ---------------------------------------------------------------------------
# Notification
# ---------------------------------------------------------------------------

def send_test_notification():
    url = "https://ntfy.sh/" + config.NTFY_TOPIC
    headers = {
        "Title":    "Focus Device Test",
        "Priority": "high",
        "Tags":     "test_tube"}
    message = "Testing! Your Focus Device notifications are working."

    print("Sending... ", end="")
    try:
        response = urequests.post(url, data=message, headers=headers)
        code = response.status_code
        response.close()
        if code == 200:
            print(f"OK (HTTP {code}) — check your phone")
        else:
            print(f"Unexpected response: HTTP {code}")
    except Exception as e:
        print(f"FAILED: {e}")

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

print("=" * 42)
print("  ntfy.sh Notification Test")
print(f"  Topic: {config.NTFY_TOPIC}")
print(f"  Sending every {SEND_INTERVAL_MS // 1000}s — stop with Thonny Stop button")
print("=" * 42)

if connect_wifi():
    count = 0
    while True:
        count += 1
        print(f"[{count}] ", end="")
        send_test_notification()
        time.sleep_ms(SEND_INTERVAL_MS)
