# test_notification.py
# Manually test ntfy.sh push notifications from the ESP32.
#
# How to use:
#   1. Fill in config.py: WIFI_SSID, WIFI_PASSWORD, NTFY_TOPIC
#   2. Install the ntfy app on your phone and subscribe to your NTFY_TOPIC
#   3. Upload this file and config.py to the ESP32, then run this file in Thonny
#   4. Press SPACE in the Thonny Shell to fire a test notification
#   5. Press Q to quit

import sys
import select
import time
import network
import urequests
import config

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
        "Tags":     "test_tube"
    }
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
# Keyboard helper — non-blocking single character read from Thonny shell
# ---------------------------------------------------------------------------

_poll = select.poll()
_poll.register(sys.stdin, select.POLLIN)

def read_key():
    """Return the next character from stdin, or None if nothing is waiting."""
    if _poll.poll(0):            # 0 ms timeout = non-blocking
        return sys.stdin.read(1)
    return None

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

print("=" * 42)
print("  ntfy.sh Notification Test")
print(f"  Topic: {config.NTFY_TOPIC}")
print("=" * 42)

if connect_wifi():
    print()
    print("Ready.")
    print("  SPACE  →  send test notification")
    print("  Q      →  quit")
    print()

    count = 0
    while True:
        key = read_key()

        if key == ' ':
            count += 1
            print(f"[{count}] ", end="")
            send_test_notification()

        elif key in ('q', 'Q'):
            print("Exiting.")
            break

        time.sleep_ms(50)   # keep the loop light on CPU
