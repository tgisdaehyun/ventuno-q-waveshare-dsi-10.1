#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Endless, inaudible 20 Hz sine at -40 dBFS on stdout (s16le, 48 kHz, stereo).

The speaker amplifier on the Waveshare carrier switches itself off when its input is silent and
pops when it wakes up again. Feeding it this signal all the time keeps it awake.
"""
import math, struct, sys
SR, HZ, DB = 48000, 20, -40
amp = int(32767 * 10 ** (DB / 20))
period = SR // HZ                                    # one full cycle, so the block loops seamlessly
block = b"".join(struct.pack("<hh", v, v) for v in
                 (int(amp * math.sin(2 * math.pi * i / period)) for i in range(period))) * HZ  # 1 s
out = sys.stdout.buffer
while True:
    out.write(block)
