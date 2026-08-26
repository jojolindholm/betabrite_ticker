# Betabrite Ticker

Drive a **Betabrite 1196** LED display as a news ticker. Pulls headlines from RSS feeds and scrolls them across the sign.

## Requirements

- **Python 3.10+**
- **libusb** (USB backend):
  ```bash
  brew install libusb
  ```
- **pyusb** (Python USB wrapper):
  ```bash
  pip install pyusb
  ```
- **pyserial** (only for serial-connected signs):
  ```bash
  pip install pyserial
  ```

## Hardware

This project targets the Betabrite 1196 with a **USB-BULK interface** (VID `0x8765`, PID `0x1234`, "ADAPTIVE USB-BULK Device"). It communicates using the **Alpha Sign Communications Protocol** over USB bulk transfers.

If your sign uses a serial port (RS-232 / USB-serial adapter), use `betabrite_serial.py` instead.

## Files

| File | Purpose |
|---|---|
| `betabrite_usb.py` | Core library — USB protocol driver for the Betabrite 1196 (pyusb) |
| `news_ticker.py` | RSS news ticker — fetches headlines and scrolls them on the sign |
| `setup_memory.py` | One-shot utility — configure the sign's memory allocation |
| `betabrite_serial.py` | Serial-based driver (pyserial) for RS-232 connected signs |

## Usage

### 1. Memory Setup (first time only)

Before using the ticker, allocate file space on the sign:

```bash
python setup_memory.py --size 4096
```

This clears the sign's memory and allocates 4096 bytes for text file A. Max is 65535.

### 2. News Ticker

Run the rotating RSS ticker with default feeds (DN, SVT, NYT, Guardian):

```bash
python news_ticker.py
```

**Options:**

| Flag | Description |
|---|---|
| `--feed NAME=URL` | Add a custom feed (repeatable). Replaces defaults. |
| `--scroll-speed N` | Scroll speed in chars/sec (default: 6, lower = slower) |
| `--max-items N` | Max headlines per feed (default: 5) |
| `--max-chars N` | Max text length sent to sign (default: 350) |
| `--intro-seconds N` | Seconds to show feed name before scrolling (default: 5) |
| `--once` | Fetch one feed and exit |

**Examples:**

```bash
# Custom feeds only
python news_ticker.py --feed "BBC=https://feeds.bbci.co.uk/news/rss.xml"

# Quiet scroll, longer intro
python news_ticker.py --scroll-speed 4 --intro-seconds 10

# Single-shot mode
python news_ticker.py --once
```

### 3. Send a one-off message

```bash
python -c "import betabrite_usb as bb; bb.write_message('Hello World!', mode='ROTATE')"
```

### 4. Serial sign (alternative hardware)

```bash
python betabrite_serial.py
```

Edit the port in the script if needed (e.g. `COM1` on Windows).

## Display Modes

| Mode | Description |
|---|---|
| `ROTATE` | Scroll characters right-to-left (default) |
| `HOLD` | Static display |
| `FLASH` | Flashing text |
| `ROLL_UP` / `ROLL_DOWN` / `ROLL_LEFT` / `ROLL_RIGHT` | Roll in from edge |
| `WIPE_UP` / `WIPE_DOWN` / `WIPE_LEFT` / `WIPE_RIGHT` | Wipe reveal |
| `SCROLL` | Continuous scroll |
| `TWINKLE` / `SPARKLE` / `SNOW` | Animated effects |
| `INTERLOCK` / `SWITCH` / `SLIDE` | Transition effects |
| `SPRAY` / `STARBURST` / `WELCOME` | More effects |

## Protocol Details

The Betabrite 1196 uses the **Alpha Sign Communications Protocol** with these control bytes:

- `SOH` (0x01) — Start of Header
- `STX` (0x02) — Start of Text
- `EOT` (0x04) — End of Transmission
- `ESC` (0x1B) — Escape (precedes display mode)
- `FS`  (0x1C) — File Separator (inline color codes)

Color is applied inline: `\x1C2` = green, `\x1C7` = orange, etc.

The sign uses **CP437 (PC-8)** character encoding, so Swedish/European accented characters (å, ä, ö, é, ü) render correctly.

## License

MIT
