# notifications.py — ntfy.sh push notification wrapper

import urequests
import time
import config

_last_notify_time = 0


def send_notification(message, title="Focus Device", priority="high", tags="warning"):
    """
    Send a push notification via ntfy.sh.
    Returns True on success, False on failure or cooldown.
    """
    global _last_notify_time

    now = time.time()
    if now - _last_notify_time < config.NOTIFY_COOLDOWN:
        print("[notifications] skipped — cooldown active")
        return False

    url     = "https://ntfy.sh/" + config.NTFY_TOPIC
    headers = {
        "Title":    title,
        "Priority": priority,
        "Tags":     tags
    }

    try:
        response = urequests.post(url, data=message, headers=headers)
        response.close()
        _last_notify_time = now
        print("[notifications] sent:", message)
        return True
    except Exception as e:
        print("[notifications] FAILED:", e)
        return False


def send_session_start():
    """Called in STARTING state — device just turned on."""
    send_notification(
        message="Session started! Place your phone on the device to begin.",
        title="Focus Device",
        priority="default",
        tags="stopwatch"
    )


def send_first_warning():
    """Called immediately when phone leaves pad (GRACE state entry)."""
    send_notification(
        message="Put your phone down and get back to work!",
        title="Focus Device",
        priority="high",
        tags="warning"
    )


def send_gentle_reminder():
    """
    Called once at the 30s mark — kind nudge before the alarm starts.
    Bypasses cooldown: this is a precisely timed single event, not user-triggered.
    """
    url     = "https://ntfy.sh/" + config.NTFY_TOPIC
    headers = {"Title": "Focus Device", "Priority": "default", "Tags": "bell"}
    try:
        response = urequests.post(
            url,
            data="Heads up — alarm starts in 5 seconds. Put your phone down!",
            headers=headers
        )
        response.close()
        print("[notifications] gentle reminder sent")
    except Exception as e:
        print("[notifications] FAILED:", e)


def send_alarm_spam():
    """
    Called repeatedly during ALARM state on ALARM_NOTIFY_INTERVAL cadence.
    Bypasses cooldown — the interval is managed by main.py, not the cooldown guard.
    """
    url     = "https://ntfy.sh/" + config.NTFY_TOPIC
    headers = {"Title": "FOCUS DEVICE", "Priority": "urgent", "Tags": "rotating_light"}
    try:
        response = urequests.post(
            url,
            data="PUT YOUR PHONE DOWN!",
            headers=headers
        )
        response.close()
        print("[notifications] alarm spam sent")
    except Exception as e:
        print("[notifications] FAILED:", e)


def send_escalation_warning():
    """Optional second notification sent during ALARM state."""
    send_notification(
        message="Still distracted? The alarm is getting louder.",
        title="FOCUS DEVICE",
        priority="urgent",
        tags="rotating_light"
    )


def send_btn_blocked():
    """Called when 5s power-off hold is attempted but phone is not on the device."""
    send_notification(
        message="Place your phone on the device before ending the session.",
        title="Focus Device",
        priority="default",
        tags="hand"
    )


def send_session_end(duration_s, pickups, phone_off_s=0):
    """
    Called in STOPPING state — session complete.
    duration_s:   total session length in seconds
    pickups:      number of times phone was removed (GRACE entries)
    phone_off_s:  total seconds the phone was off the device
    """
    global _last_notify_time
    _last_notify_time = 0   # bypass cooldown — always send this one
    duration_min  = duration_s // 60
    phone_off_min = phone_off_s // 60
    phone_off_sec = phone_off_s % 60
    message = "Session: {} min | Pickups: {} | Phone time: {}m {}s".format(
        duration_min, pickups, phone_off_min, phone_off_sec)
    send_notification(
        message=message,
        title="Session Complete",
        priority="default",
        tags="white_check_mark"
    )


def reset_cooldown():
    """Reset cooldown timer — call when phone is returned to pad."""
    global _last_notify_time
    _last_notify_time = 0
