#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Convert upstream waveshare_10_1_a_init() into a 1090-style init table for a given lane count."""
import re, sys
src = open(sys.argv[1]).read(); lanes = int(sys.argv[2])
m = re.search(r'static int waveshare_10_1_a_init\(struct jadard \*jadard\)\n\{(.*?)\n\}\n', src, re.S)
body = m.group(1).split('\n')
out = []; cond = [True]   # stack of active flags
pending_single = None     # for brace-less if/else: applies to next statement only
def emit(line):
    s = line.strip()
    mm = re.match(r'mipi_dsi_dcs_write_seq_multi\(&dsi_ctx, (0x[0-9a-fA-F]+), (0x[0-9a-fA-F]+)\);', s)
    if mm: out.append((int(mm.group(1),16), int(mm.group(2),16))); return
    mm = re.match(r'jd9365da_switch_page\(&dsi_ctx, (0x[0-9a-fA-F]+)\);', s)
    if mm: out.append((0xE0, int(mm.group(1),16))); return
    if s == 'jadard_enable_standard_cmds(&dsi_ctx);':
        out.extend([(0xE1,0x93),(0xE2,0x65),(0xE3,0xF8),(0x80, 0x01 if lanes==2 else 0x03)]); return
    if s.startswith(('struct mipi_dsi_multi_context','mipi_dsi_dcs_exit_sleep_mode_multi','msleep','mipi_dsi_dcs_set_display_on_multi','return')) or not s: return
    raise SystemExit('unparsed: '+s)
def ev(c):
    mm = re.match(r'jadard->dsi->lanes (==|!=) 4', c); assert mm, c
    return (lanes==4) if mm.group(1)=='==' else (lanes!=4)
last_if = None; single = None
for line in body:
    s = line.strip()
    mm = re.match(r'if \((.*)\) \{$', s)
    if mm: last_if = ev(mm.group(1)); cond.append(last_if); continue
    if re.match(r'\} else\s+\{$', s): cond.pop(); cond.append(not last_if); continue
    if s == '}': cond.pop(); continue
    mm = re.match(r'if \((.*)\)$', s)
    if mm: last_if = ev(mm.group(1)); single = last_if; continue
    if s == 'else': single = not last_if; continue
    act = all(cond) and (single is None or single)
    single = None
    if act: emit(line)
assert cond == [True]
print('/* generated from upstream waveshare_10_1_a_init(), %d lanes: %d commands */' % (lanes, len(out)))
for r, v in out: print('\t{ .data = { 0x%02X, 0x%02X } },' % (r, v))
