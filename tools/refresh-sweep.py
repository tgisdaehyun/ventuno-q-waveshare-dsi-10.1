#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Refresh-rate sweep on DSI-1 through mutter (temporary config), with an on-screen label per step."""
import subprocess, re, time, sys
CYCLES = int(sys.argv[1]) if len(sys.argv) > 1 else 4; STEP_S = 8
B = ["gdbus", "call", "--session", "--dest", "org.gnome.Mutter.DisplayConfig", "--object-path",
     "/org/gnome/Mutter/DisplayConfig", "--method"]
def state():
    s = subprocess.run(B + ["org.gnome.Mutter.DisplayConfig.GetCurrentState"], capture_output=True, text=True).stdout
    serial = int(re.match(r"\(uint32 (\d+)", s).group(1))
    modes = {round(float(r)): mid for mid, r in re.findall(r"\('(\d+x\d+@[\d.]+)', \d+, \d+, ([\d.]+)", s)}
    return serial, modes
def apply(mid):
    serial, _ = state()
    cfg = f'[(0, 0, 1.25, uint32 0, true, [("DSI-1", "{mid}", @a{{sv}} {{}})])]'
    r = subprocess.run(B + ["org.gnome.Mutter.DisplayConfig.ApplyMonitorsConfig", str(serial), "1", cfg, "@a{sv} {}"],
                       capture_output=True, text=True)
    return r.returncode == 0, r.stderr.strip()
nid = None
def label(text):
    global nid
    cmd = ["notify-send", "-p", "-u", "critical", "-t", "0"] + (["-r", nid] if nid else []) + [text, "refresh sweep"]
    out = subprocess.run(cmd, capture_output=True, text=True).stdout.strip()
    if out: nid = out
_, modes = state()
order = [60, 48, 50, 52, 54, 56, 57, 58, 59, 61, 62, 63, 64, 66, 68, 70, 72]
print("modes", sorted(modes), flush=True)
try:
    for c in range(CYCLES):
        for i, hz in enumerate(order, 1):
            ok, err = apply(modes[hz]); print(c, i, hz, ok, err, flush=True)
            time.sleep(1); label(f"TEST {i}:  {hz} Hz"); time.sleep(STEP_S)
finally:
    apply(modes[60]); label("done: back to 60 Hz")
