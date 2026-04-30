# test_speaker.py
# Speaker volume test — adjust intensity and play tones.
#
# Controls:
#   +  or  =    increase volume by 5%
#   -           decrease volume by 5%
#   1 – 9       jump to 10% – 90% instantly
#   0           jump to 100%
#   SPACE       play one beep at current volume
#   C           toggle continuous play on / off
#   Q           quit

import sys
import select
import time
from machine import DAC, Pin
import config

# ---------------------------------------------------------------------------
# DAC / audio
# ---------------------------------------------------------------------------

_dac = DAC(Pin(config.PIN_DAC))
_dac.write(128)

def _play_tone(freq_hz, duration_ms, volume):
    amp            = int(127 * max(0.0, min(1.0, volume)))
    high           = 128 + amp
    low            = 128 - amp
    half_period_us = 500_000 // freq_hz
    deadline = time.ticks_add(time.ticks_ms(), duration_ms)
    state = True
    while time.ticks_diff(deadline, time.ticks_ms()) > 0:
        _dac.write(high if state else low)
        state = not state
        time.sleep_us(half_period_us)
    _dac.write(128)

def play_beep(volume):
    _play_tone(880, 250, volume)
    _play_tone(440, 250, volume)

# ---------------------------------------------------------------------------
# Keyboard
# ---------------------------------------------------------------------------

_poll = select.poll()
_poll.register(sys.stdin, select.POLLIN)

def read_key():
    if _poll.poll(0):
        return sys.stdin.read(1).lower()
    return None

# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------

BAR_WIDTH = 20

def _bar(volume):
    filled = round(volume * BAR_WIDTH)
    return "[" + "#" * filled + "-" * (BAR_WIDTH - filled) + "]"

def print_status(volume, continuous):
    pct    = int(volume * 100)
    mode   = "  [CONTINUOUS]" if continuous else ""
    print("  Volume: {:>3}%  {}{}    ".format(pct, _bar(volume), mode), end='\r')

def print_header():
    print("\n" + "=" * 44)
    print("  Speaker Volume Test")
    print("=" * 44)
    print("  +/=   increase 5%   |  -    decrease 5%")
    print("  1–9   jump 10–90%   |  0    jump 100%")
    print("  SPACE play beep     |  C    toggle continuous")
    print("  Q     quit")
    print()

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run():
    volume     = 0.50   # start at 50%
    continuous = False
    step       = 0.05

    print_header()
    print_status(volume, continuous)

    while True:
        key = read_key() or ''

        if key == 'q':
            _dac.write(128)
            print("\nExiting.")
            return

        elif key in ('+', '='):
            volume = min(1.0, round(volume + step, 2))
            print_status(volume, continuous)

        elif key == '-':
            volume = max(0.0, round(volume - step, 2))
            print_status(volume, continuous)

        elif key in ('1','2','3','4','5','6','7','8','9'):
            volume = float(key) * 0.10
            print_status(volume, continuous)

        elif key == '0':
            volume = 1.0
            print_status(volume, continuous)

        elif key == ' ':
            print()   # move off the status line
            print("  Playing {:>3}% ...".format(int(volume * 100)))
            play_beep(volume)
            print_status(volume, continuous)

        elif key == 'c':
            continuous = not continuous
            print_status(volume, continuous)

        # Continuous play — check for key between each beep
        if continuous:
            # Play one tone at a time so key checks happen every 250 ms
            _play_tone(880, 250, volume)
            key2 = read_key() or ''
            if key2 == 'c':
                continuous = False
                print_status(volume, continuous)
            elif key2 == 'q':
                _dac.write(128)
                print("\nExiting.")
                return
            elif key2 in ('+', '='):
                volume = min(1.0, round(volume + step, 2))
                print_status(volume, continuous)
            elif key2 == '-':
                volume = max(0.0, round(volume - step, 2))
                print_status(volume, continuous)
            elif key2 in '123456789':
                volume = int(key2) * 0.10
                print_status(volume, continuous)
            elif key2 == '0':
                volume = 1.0
                print_status(volume, continuous)

            _play_tone(440, 250, volume)
        else:
            time.sleep_ms(50)

run()
