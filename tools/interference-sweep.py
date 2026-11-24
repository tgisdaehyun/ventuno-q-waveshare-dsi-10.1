#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Band-interference sweep: one suspect toggled per step, big step number on a gray text console."""
import os, fcntl, subprocess, time, glob, sys
TTY = "/dev/tty3"; STEP_S = 10; CYCLES = int(sys.argv[1]) if len(sys.argv) > 1 else 6
FONT = {"1":["..#..",".##..","..#..","..#..","..#..","..#..",".###."],"2":[".###.","#...#","....#","...#.","..#..",".#...","#####"],
"3":[".###.","#...#","....#","..##.","....#","#...#",".###."],"4":["...#.","..##.",".#.#.","#..#.","#####","...#.","...#."],
"5":["#####","#....","####.","....#","....#","#...#",".###."],"6":[".###.","#....","####.","#...#","#...#","#...#",".###."],
"7":["#####","....#","...#.","..#..","..#..","..#..","..#.."],"8":[".###.","#...#","#...#",".###.","#...#","#...#",".###."]}
def show(n, text):
    rows = ["".join(("######" if c == "#" else "      ") for c in r) for r in FONT[str(n)] for _ in range(4)]
    out = "\033[30;47m\033[2J\033[H\033[?25l\n\n"
    out += "".join(" " * 60 + r + "\n" for r in rows)
    out += "\n\n" + " " * 50 + f"STEP {n}:  {text}\n"
    open(TTY, "w").write(out)
def sh(c): subprocess.run(c, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
def pca(reg, val):
    fd = os.open("/dev/i2c-13", os.O_RDWR); fcntl.ioctl(fd, 0x0703, 0x26); os.write(fd, bytes([reg, val])); os.close(fd)
hw = os.path.dirname([f for f in glob.glob("/sys/class/hwmon/*/name") if "emc" in open(f).read()][0])
pwm0 = open(hw + "/pwm1").read().strip()
def fan(v): open(hw + "/pwm1", "w").write(str(v))
def pin_low(bit):
    pca(2, 0xFF & ~(1 << bit)); pca(6, 0xFF & ~(1 << bit))
def pin_restore(): pca(6, 0xFF); pca(2, 0xFF)
sh("chvt 3"); time.sleep(1)
try:
    for cyc in range(CYCLES):
        show(1, "BASELINE (nothing changed)"); time.sleep(STEP_S)
        show(2, "camera server stopped"); sh("systemctl stop cam-server"); time.sleep(STEP_S); sh("systemctl start cam-server")
        show(3, "fan stopped"); fan(0); time.sleep(STEP_S)
        show(4, "fan full speed"); fan(255); time.sleep(STEP_S); fan(pwm0)
        show(5, "carrier IO pin 0 low"); pin_low(0); time.sleep(STEP_S); pin_restore()
        show(6, "carrier IO pin 2 low"); pin_low(2); time.sleep(STEP_S); pin_restore()
        show(7, "audio stream running"); p = subprocess.Popen("aplay -q -D plughw:0,0 -f S16_LE -r 48000 -c 2 /dev/zero", shell=True, stderr=subprocess.DEVNULL); time.sleep(STEP_S); p.terminate(); sh("pkill -x aplay")
        show(8, "CPU fully loaded"); ps = [subprocess.Popen(["sh", "-c", "while :; do :; done"]) for _ in range(8)]; time.sleep(STEP_S); [q.kill() for q in ps]
finally:
    fan(pwm0); pin_restore(); sh("systemctl start cam-server"); sh("pkill -x aplay")
    open(TTY, "w").write("\033[0m\033[2J\033[H\033[?25h"); sh("chvt 2")
