#!/usr/bin/env python3
"""Mouse click in a test VM through QMP (usb-tablet = absolute pointer). usage: click.py uefi X Y [W H] [double]
X,Y in screen pixels (default screen 1280x800)."""
import json, socket, sys, time
mode, x, y = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
W = int(sys.argv[4]) if len(sys.argv) > 4 else 1280; H = int(sys.argv[5]) if len(sys.argv) > 5 else 800
s = socket.socket(socket.AF_UNIX); s.connect(f"test/tmp/qmp-{mode}.sock"); f = s.makefile("rw")
f.readline(); f.write(json.dumps({"execute": "qmp_capabilities"}) + "\n"); f.flush(); f.readline()
def send(events):
    f.write(json.dumps({"execute": "input-send-event", "arguments": {"events": events}}) + "\n"); f.flush(); f.readline()
ax = lambda a, v: {"type": "abs", "data": {"axis": a, "value": int(v)}}
send([ax("x", x / W * 32767), ax("y", y / H * 32767)]); time.sleep(0.3)
for _ in range(2 if "double" in sys.argv else 1):
    send([{"type": "btn", "data": {"down": True, "button": "left"}}]); time.sleep(0.1)
    send([{"type": "btn", "data": {"down": False, "button": "left"}}]); time.sleep(0.2)
