#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""apply / roll back the Waveshare 10.1" DSI overlay on the VENTUNO Q device tree.

Same procedure as arduino-linux-config (internal/dto): the boot firmware reads
combined-dtb.dtb from the dtb_a partition; the arduino,monza tree inside it is replaced by
fdtoverlay(base monza tree + overlay). The base always comes from the kernel package, so
`rollback` simply writes the pristine file back.

  ws-dsi-dtb.py apply | rollback | status
Note: `arduino-linux-config hw enable/disable/reload` (also run on kernel updates) rewrites
dtb_a without this overlay; run `apply` again afterwards.
"""
import os, struct, subprocess, sys, hashlib, shutil
KVER = os.uname().release
BASE = f"/lib/firmware/{KVER}/device-tree/qcom/combined-dtb.dtb"
DTBO = "/var/lib/ws-dsi/monaco-monza-waveshare-10.1-dsi-touch-a.dtbo"
STATE = "/var/lib/ws-dsi"
PART = "/dev/disk/by-partlabel/dtb_a"
MNT = "/run/ws-dsi/dtb"
MAGIC = b"\xd0\x0d\xfe\xed"

def split(data):
    trees, off = [], 0
    while off + 8 <= len(data):
        if data[off:off+4] != MAGIC: raise SystemExit(f"no fdt magic at {off}")
        size = struct.unpack(">I", data[off+4:off+8])[0]
        end = off + size
        while end + 8 <= len(data) and data[end:end+4] != MAGIC: end += 1
        if end + 8 > len(data): end = len(data)
        trees.append(data[off:end]); off = end
    return trees

def monza_index(trees):
    for i, t in enumerate(trees):
        if b"arduino,monza" in t: return i
    raise SystemExit("no arduino,monza tree in combined dtb")

def sha(b): return hashlib.sha256(b).hexdigest()[:16]

def mounted(fn):
    os.makedirs(MNT, exist_ok=True)
    subprocess.run(["mount", "-t", "vfat", PART, MNT], check=True)
    try: return fn()
    finally:
        os.sync(); subprocess.run(["umount", MNT], check=True)

def build():
    trees = split(open(BASE, "rb").read()); i = monza_index(trees)
    os.makedirs("/run/ws-dsi", exist_ok=True)
    src, out = "/run/ws-dsi/monza.dtb", "/run/ws-dsi/monza-ws.dtb"
    size = struct.unpack(">I", trees[i][4:8])[0]
    open(src, "wb").write(trees[i][:size])
    subprocess.run(["fdtoverlay", "-i", src, "-o", out, DTBO], check=True)
    new = open(out, "rb").read()
    if b"waveshare,10.1-dsi-touch-a" not in new: raise SystemExit("overlay not in result")
    trees[i] = new
    return b"".join(trees)

def write(blob):
    def w():
        cur = os.path.join(MNT, "combined-dtb.dtb")
        os.makedirs(STATE, exist_ok=True)
        if os.path.exists(cur):
            shutil.copyfile(cur, os.path.join(STATE, "combined-dtb.dtb.before-last-write"))
        tmp = cur + ".tmp"
        with open(tmp, "wb") as f:
            f.write(blob); f.flush(); os.fsync(f.fileno())
        os.replace(tmp, cur)
        back = open(cur, "rb").read()
        if back != blob: raise SystemExit("read-back mismatch")
        print(f"dtb_a combined-dtb.dtb written: {len(blob)} bytes sha {sha(blob)}")
    mounted(w)

def status():
    def r(): return open(os.path.join(MNT, "combined-dtb.dtb"), "rb").read()
    cur = mounted(r); base = open(BASE, "rb").read()
    t = split(cur); m = t[monza_index(t)]
    print(f"dtb_a: {len(cur)} bytes sha {sha(cur)}; pristine({KVER}) sha {sha(base)}")
    print("dtb_a == pristine:", cur == base)
    print("overlay present in dtb_a:", b"waveshare,10.1-dsi-touch-a" in m)
    try: live = open("/proc/device-tree/soc@0/display-subsystem@ae00000/dsi@ae94000/panel@0/compatible","rb").read()
    except OSError: live = b""
    print("overlay active in running kernel:", b"waveshare,10.1" in live)

cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
if os.geteuid() != 0: raise SystemExit("run as root")
if cmd == "apply": write(build())
elif cmd == "rollback": write(open(BASE, "rb").read())
elif cmd == "status": status()
else: raise SystemExit(__doc__)
