# test_capacitance.py
# Prints the raw TouchPad value from GPIO4 every second.
# Lower value = more capacitance detected (phone / hand present).
# Use these readings to set TOUCH_THRESHOLD in config.py.

from machine import TouchPad, Pin
import time
import config

touch = TouchPad(Pin(config.PIN_TOUCH_PHONE))

print("=" * 36)
print("  Capacitance Sensor Test — GPIO32")
print("  Lower value = object detected")
print(f"  Current threshold: {config.TOUCH_THRESHOLD}")
print("  Stop with Thonny Stop button")
print("=" * 36)

while True:
    val = touch.read()
    detected = val < config.TOUCH_THRESHOLD
    print(f"Touch value: {val:>5}   {'<<< DETECTED' if detected else ''}")
    time.sleep(0.1)
