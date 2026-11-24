# Waveshare UNO-Q-DSI-TOUCH-10.1A on the Arduino VENTUNO Q

Unofficial bring-up of the Waveshare **UNO-Q-DSI-TOUCH-10.1A** (10.1" 800x1280 MIPI-DSI panel with
capacitive touch, speakers and camera connectors, made for the UNO Q) on the **Arduino VENTUNO Q**
(Qualcomm QCS8300, device-tree compatible `arduino,monza`).

Waveshare lists the VENTUNO Q as compatible, but at the time of writing the VENTUNO Q system image
has no support for it: `arduino-linux-config` only knows the display on the UNO Q, the kernel has
no overlay for it and its panel driver does not know the 10.1" panel. This repository is what it
took to make it work anyway.

**Working:** picture, touch, backlight control, landscape orientation from the first boot message
on, speakers.
**Not working while this is installed:** HDMI output and HDMI audio, and the CAMERA0 connector
(see [Trade-offs](#trade-offs)).

> This is a hobby port, tested on one board with one kernel. It writes to the device-tree
> partition of the board. A broken device tree can leave the board unbootable until it is reflashed
> over USB, so **back up the `dtb_a` partition first** and make sure you know how to reflash.
> No warranty.

## Tested with

| | |
|---|---|
| Board | Arduino VENTUNO Q (ABX00181) |
| Image | Ubuntu 24.04, kernel `6.8.0-1090-qcom` |
| `arduino-linux-config` | 0.3.0 |
| Display | Waveshare UNO-Q-DSI-TOUCH-10.1A (panel `10.1-DSI-TOUCH-A`, JD9365DA controller, Goodix GT9271 touch) |
| Desktop | GNOME 46 on Wayland |

## How the hardware is wired (what the overlay relies on)

Worked out from the public VENTUNO Q schematic and pinout and by probing the board:

- **One DSI port, shared with HDMI.** The DSI lanes go through a mux whose select input is the
  HDMI hot-plug line. No HDMI cable: the lanes go to the JMEDIA connector (the panel). HDMI cable
  plugged in: they go to the on-board ADV7535 HDMI bridge and the panel goes dark. Nothing switches
  this from software.
- **The panel's I2C bus is on JMEDIA pins 51/53 = SoC GPIO58 (SCL) / GPIO57 (SDA).** On it:
  `0x45` the panel's microcontroller (power rails, resets, backlight), `0x5d` the Goodix touch
  controller, `0x26` a PCA9555 I/O expander on the carrier.
- Those two GPIOs are also the camera control bus of the CAMERA0 connector (CCI0 master 0), which
  is owned by Qualcomm's camera stack and is not a normal Linux I2C adapter. The overlay therefore
  bit-bangs the bus with `i2c-gpio` (the stock device tree does the same for another bus) and
  takes those pins away from the camera stack.
- The panel microcontroller is the one the mainline `gpio-waveshare-dsi` driver handles
  (`waveshare,dsi-touch-gpio`); that driver is already in the kernel.

## What is in here

| Path | What |
|---|---|
| `overlay/monaco-monza-waveshare-10.1-dsi-touch-a.dtso` | Device-tree overlay: I2C bus, panel MCU, touch, panel, DSI routed to the panel, HDMI bridge and its audio link disabled, CAMERA0 sensor slots disabled |
| `module/panel-jadard-jd9365da-h3.c` | The kernel's JD9365DA panel driver (from `6.8.0-1090-qcom`) with the 10.1" panel added. Init tables converted from mainline Linux |
| `scripts/ws-dsi-dtb.py` | Applies / rolls back the overlay on the `dtb_a` partition |
| `config/` | Kernel command line, initramfs module list, GNOME monitor entry, audio service files |
| `scripts/amp-keepalive.py` | Keeps the carrier's speaker amplifier awake (no pops) |
| `tools/` | Init-table converter and the two test scripts used to hunt the display interference |

## Install

Everything below runs on the board. Read the scripts before running them.

### 1. Back up the device-tree partition

```sh
sudo dd if=/dev/disk/by-partlabel/dtb_a of=dtb_a.img bs=1M
```

Copy `dtb_a.img` off the board.

### 2. Build and install the panel driver

```sh
sudo apt install gcc-13 make libc6-dev          # kernel headers are already on the image
cd module
make -C /lib/modules/$(uname -r)/build M=$PWD CC=aarch64-linux-gnu-gcc-13 modules
sudo mkdir -p /lib/modules/$(uname -r)/updates
sudo cp panel-jadard-jd9365da-h3.ko /lib/modules/$(uname -r)/updates/
sudo depmod -a
```

`updates/` takes precedence over the stock module. The kernel will log that an out-of-tree,
unsigned module was loaded.

### 3. Build and apply the overlay

```sh
sudo mkdir -p /var/lib/ws-dsi
dtc -@ -I dts -O dtb -o monaco-monza-waveshare-10.1-dsi-touch-a.dtbo \
    overlay/monaco-monza-waveshare-10.1-dsi-touch-a.dtso
sudo cp monaco-monza-waveshare-10.1-dsi-touch-a.dtbo /var/lib/ws-dsi/
sudo install -m 755 scripts/ws-dsi-dtb.py /usr/local/sbin/ws-dsi-dtb
sudo ws-dsi-dtb apply
sudo ws-dsi-dtb status
```

`ws-dsi-dtb` does what `arduino-linux-config` does for its own overlays: the boot firmware loads
`combined-dtb.dtb` from the `dtb_a` partition, a concatenation of device trees for several boards.
The script takes the pristine file from the kernel package, runs `fdtoverlay` on the
`arduino,monza` tree inside it and writes the result to `dtb_a`. The running kernel cannot load
overlays at run time (`CONFIG_OF_OVERLAY` is off), so a reboot is needed.

Unplug any HDMI cable, then reboot. The panel should come up in portrait.

### 4. Orientation, refresh rate, boot splash

Copy `config/grub.d-zz-ws-dsi.cfg` to `/etc/default/grub.d/zz-ws-dsi.cfg`, adjust, then
`sudo update-grub`.

- `video=DSI-1:panel_orientation=left_side_up` (or `right_side_up`) rotates the kernel console,
  the plymouth splash and GNOME together. With this set, do **not** also rotate the display in
  GNOME, or it is rotated twice. Which of the two you want only depends on which way round the
  unit sits; ours is flipped so the ports stay reachable.
- `panel_jadard_jd9365da_h3.ws_vrefresh=68` sets the default refresh rate, `ws_sweep=1` adds
  48–72 Hz as selectable modes in *Settings > Displays*.

To get the splash on the panel early, add the lines from `config/initramfs-modules.snippet` to
`/etc/initramfs-tools/modules` and run `sudo update-initramfs -u`.

`config/monitors.xml.snippet` is the GNOME entry we ended up with (scale 1.25, 68 Hz).

### 5. Speakers

The carrier's speakers hang on the Line Out of the board's MAX98091 codec.

- `config/lineout.service` → `/etc/systemd/system/`, then `sudo systemctl enable --now lineout`
  and `sudo alsactl store`. It selects the `Lineout` device of the stock ALSA UCM profile once the
  sound card is up, and it keeps the codec's DAC and line output powered even when no stream is
  open. Without that, every open/close of the PCM power-cycles the output stage (PipeWire alone
  does it three times while probing the card at start-up), and each cycle is a loud pop on the
  speakers. The trick is a muted ADC → sidetone → DAC route: for the kernel's power management
  (DAPM) that is an active path, so nothing is switched off, while no input signal reaches the
  speakers.
- PipeWire offers no UCM profile for this card, so the desktop only shows "Dummy Output".
  `config/51-lineout.lua` → `~/.config/wireplumber/main.lua.d/` switches the card to the
  `pro-audio` profile, makes PCM 0 the default sink and stops it from being suspended
  (WirePlumber 0.4 Lua config).
- The speaker amplifier on the carrier switches itself off when its input is silent and pops
  when it wakes up. `scripts/amp-keepalive.py` + `config/amp-keepalive.service` (a systemd *user*
  service; adjust the script path) play an inaudible 20 Hz sine at -40 dBFS all the time, which
  keeps it awake. Turning the output volume far down weakens that signal too.

## The moving bands, and why the panel runs at 68 Hz

At the panel's nominal 60 Hz the picture had thick, soft bands along the panel's rows (vertical
bands when mounted landscape) that slowly drifted back and forth. They are visible on a plain
gray framebuffer, so they are not a rendering problem.

What made **no difference**:

- DSI video mode: non-burst with sync events (mainline default for this panel), sync pulses, burst
- 2 data lanes vs 4 (each with its own init table)
- the init table itself (read back from the panel: it is accepted as written)
- backlight brightness, extra 5 V on the carrier's USB-C port
- touch controller held in reset / touch polling stopped
- camera server, fan off / full, PCA9555 pins, audio stream running, CPU fully loaded

What did: **the refresh rate.** At 55 Hz the bands got much thicker. Sweeping 48–72 Hz by eye,
72 Hz was clean and 68 Hz is what we settled on as the best-looking setting. We did not find the root cause; the same panel and timings are used on the
UNO Q at 60 Hz, so this may well be specific to this board (or to our unit). If you know why,
please open an issue.

Other things learned along the way:

- The stock driver flow for the 8" panel (init commands sent in high-speed mode from `enable()`,
  burst mode) gave additional bands in the other direction. The 10.1" entry therefore follows
  mainline: init table sent in low-power mode from `prepare()`, flags
  `VIDEO | VIDEO_HSE | LPM | CLOCK_NON_CONTINUOUS`.
- A continuous DSI clock (dropping `CLOCK_NON_CONTINUOUS`) gives no picture at all with that flow.
- The Goodix node must not get `reset-gpios`: the panel MCU's GPIOs are output-only and the 6.8
  Goodix driver then fails to probe. There is no interrupt line either; the driver polls.

Module parameters for experiments (all read-only at run time, set on the kernel command line as
`panel_jadard_jd9365da_h3.<name>=<value>`):

| Parameter | Meaning |
|---|---|
| `ws_vrefresh` | refresh rate of the default mode |
| `ws_sweep` | offer 48–72 Hz modes as well |
| `ws_mode_flags` | override the DSI mode flags (hex) |
| `ws_lanes=2` | drive the panel over 2 lanes |
| `ws_readback=1` | log a few init registers read back from the panel |

`tools/refresh-sweep.py` cycles through the refresh rates from inside a GNOME session and
`tools/interference-sweep.py` toggles one suspect at a time on a gray console, each with a step
number on screen. Handy when the person looking at the panel is not the person at the keyboard.

## Trade-offs

- **No HDMI.** The HDMI bridge shares the single DSI host with the panel, so the overlay disables
  it together with the HDMI audio link. DisplayPort over USB-C is not touched by the overlay (not re-tested).
- **No CAMERA0.** Its control bus pins are used for the panel. The other camera connectors are
  not touched by the overlay (not re-tested).
- **Kernel updates undo it.** A new kernel needs the module rebuilt, and both kernel updates and
  `arduino-linux-config hw enable/disable/reload` rewrite `dtb_a` without this overlay. Run
  `sudo ws-dsi-dtb apply` again afterwards.
- Arduino has reserved a name for an official 8" overlay on the VENTUNO Q
  (`monaco-monza-dsi-waveshare,8.0-dsi-touch-a.dtbo`), so official support is probably on its
  way. When it arrives, prefer it.

## Undo

```sh
sudo ws-dsi-dtb rollback      # writes the pristine device tree back to dtb_a
sudo rm /lib/modules/$(uname -r)/updates/panel-jadard-jd9365da-h3.ko && sudo depmod -a
sudo rm /etc/default/grub.d/zz-ws-dsi.cfg && sudo update-grub
```

Remove the lines added to `/etc/initramfs-tools/modules`, run `sudo update-initramfs -u`, disable
the audio services, reboot. If the board no longer boots, restore `dtb_a.img` (or the whole image)
with Arduino's flashing tool over USB.

## Credits and licence

- Panel driver: Linux kernel `panel-jadard-jd9365da-h3.c` (GPL-2.0), as shipped in Ubuntu's
  `linux-qcom` 6.8.0-1090, plus the Waveshare 10.1" init sequence from mainline Linux.
- Overlay: derived from Arduino's UNO Q overlay
  `qrb2210-arduino-imola-carrier-media-panel-10in_touch_a-dsi.dtso` (GPL-2.0+ OR BSD-3-Clause).
- Device-tree apply logic follows [arduino-linux-config](https://github.com/arduino/arduino-linux-config).

Everything in this repository is licensed under GPL-2.0 unless a file says otherwise (the overlay
keeps its dual licence).

Not affiliated with Arduino, Waveshare or Qualcomm.
