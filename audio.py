# audio.py — square-wave tone generation via ESP32 DAC → PAM8302 amp

from machine import DAC, Pin
import time
import config

_dac = DAC(Pin(config.PIN_DAC))  # DAC2 on GPIO26

# Set DAC to midpoint on import so the amp sees silence immediately.
_dac.write(128)


def _play_square_tone(freq_hz, duration_ms, volume):
    """
    Block for duration_ms while driving a square wave at freq_hz.
    volume is 0.0–1.0 and scales DAC amplitude around the 128 midpoint.
    """
    amp           = int(127 * max(0.0, min(1.0, volume)))
    high          = 128 + amp
    low           = 128 - amp
    half_period_us = 500_000 // freq_hz   # µs per half-cycle

    deadline = time.ticks_add(time.ticks_ms(), duration_ms)
    state = True
    while time.ticks_diff(deadline, time.ticks_ms()) > 0:
        _dac.write(high if state else low)
        state = not state
        time.sleep_us(half_period_us)

    _dac.write(128)  # return to midpoint between tones


def play_beep(volume):
    """
    Play one two-tone beep cycle: TONE_HIGH then TONE_LOW.
    Blocks for 2 × TONE_DURATION_MS total.
    """
    _play_square_tone(config.TONE_HIGH, config.TONE_DURATION_MS, volume)
    _play_square_tone(config.TONE_LOW,  config.TONE_DURATION_MS, volume)


def silence():
    """Set DAC to midpoint — amp input sees 0 V AC, no sound."""
    _dac.write(128)
