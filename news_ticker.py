"""News ticker for the USB Betabrite. Pulls headlines from an RSS feed
and scrolls them across the display, refreshing every few minutes."""

import argparse
import html
import re
import sys
import time
import unicodedata
import urllib.request
import xml.etree.ElementTree as ET

import betabrite_usb as bb

DEFAULT_FEEDS = [
    ("DAGENS NYHETER",     "https://www.dn.se/rss/sverige"),
    ("SVT NYHETER",        "https://www.svt.se/nyheter/inrikes/rss.xml"),
    ("NEW YORK TIMES",     "https://rss.nytimes.com/services/xml/rss/nyt/World.xml"),
    ("THE GUARDIAN",       "https://www.theguardian.com/world/europe-news/rss"),
]

# Alpha Sign Protocol inline color codes: FS (0x1C) + digit.
COLOR_GREEN  = "\x1C2"
COLOR_ORANGE = "\x1C7"
DEFAULT_MAX_ITEMS = 5       # ~5 headlines fit reliably in 350 chars
DEFAULT_MAX_CHARS = 350     # empirical: USB OUT endpoint wedges past ~400 chars
DEFAULT_INTRO_SECONDS = 5
DEFAULT_SCROLL_CHARS_PER_SEC = 6   # 1196 default ROTATE speed, empirical
SIGN_WIDTH_CHARS = 80              # Betabrite 1196 = 80×7 matrix
SCROLL_PADDING_SEC = 2             # small buffer after one full pass


def fetch_headlines(url: str, max_items: int) -> list[str]:
    req = urllib.request.Request(url, headers={"User-Agent": "betabrite-ticker/1.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = resp.read()
    root = ET.fromstring(data)
    titles = []
    for item in root.iter("item"):
        t = item.findtext("title") or ""
        t = html.unescape(t).strip()
        if t:
            titles.append(t)
        if len(titles) >= max_items:
            break
    return titles


def normalize_for_sign(text: str) -> str:
    """Normalize typographic quirks and drop anything CP437 can't render.
    Swedish letters (å, ä, ö, ...) are preserved — the sign uses CP437
    so they encode cleanly downstream."""
    replacements = {
        "“": '"', "”": '"', "‘": "'", "’": "'",
        "–": "-", "—": "-", "…": "...",
    }
    text = "".join(replacements.get(c, c) for c in text)
    text = unicodedata.normalize("NFC", text)
    # Drop characters that CP437 can't represent.
    text = text.encode("cp437", "ignore").decode("cp437")
    text = re.sub(r"[\x00-\x1f]", " ", text)
    return text


def build_ticker_text(titles: list[str], max_chars: int) -> str:
    """Headlines in green, asterisk separators in orange.

    Color codes are 2 bytes each (FS + digit) and consume budget against
    max_chars just like printable characters, since the sign stores them
    in file A. We measure trimming against the *visible* length and add
    the codes afterward."""
    clean = [normalize_for_sign(t) for t in titles]
    visible_sep = "  *  "
    visible = visible_sep.join(clean)
    if len(visible) > max_chars:
        visible = visible[: max_chars - 3].rstrip() + "..."
        # Re-split so colors apply per remaining headline. Easiest: just
        # treat the truncated string as a single chunk and color it green.
        return COLOR_GREEN + visible

    colored_sep = COLOR_ORANGE + "  *  " + COLOR_GREEN
    return COLOR_GREEN + colored_sep.join(clean)


def push(dev_holder: list, text: str, mode: str = "ROTATE") -> None:
    """Send text; on USB timeout, reset the device and retry once."""
    import usb.core, usb.util
    packet = bb.build_packet(text, mode=mode)
    try:
        bb.send(dev_holder[0], packet)
    except usb.core.USBError:
        try:
            usb.util.dispose_resources(dev_holder[0])
        except Exception:
            pass
        dev_holder[0] = bb.open_display()
        bb.send(dev_holder[0], packet)


def parse_feed_arg(s: str) -> tuple[str, str]:
    if "=" not in s:
        raise argparse.ArgumentTypeError("--feed must be NAME=URL")
    name, url = s.split("=", 1)
    return name.strip(), url.strip()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--feed", action="append", type=parse_feed_arg, metavar="NAME=URL",
                   help="Repeatable. If given, replaces the default feed list.")
    p.add_argument("--scroll-speed", type=float, default=DEFAULT_SCROLL_CHARS_PER_SEC,
                   help="Characters scrolled per second (lower = slower display)")
    p.add_argument("--max-items", type=int, default=DEFAULT_MAX_ITEMS)
    p.add_argument("--max-chars", type=int, default=DEFAULT_MAX_CHARS)
    p.add_argument("--intro-seconds", type=float, default=DEFAULT_INTRO_SECONDS,
                   help="How long to hold the feed-name splash before its ticker")
    p.add_argument("--once", action="store_true",
                   help="Push one feed and exit (uses the first feed in the list)")
    args = p.parse_args()

    feeds = args.feed if args.feed else list(DEFAULT_FEEDS)

    dev_holder = [bb.open_display()]
    print(f"Connected to Betabrite. {len(feeds)} feed(s) in rotation.")

    try:
        idx = 0
        while True:
            name, url = feeds[idx]
            try:
                titles = fetch_headlines(url, args.max_items)
                print(f"[{time.strftime('%H:%M:%S')}] {name}: {len(titles)} headlines")
                if titles:
                    text = build_ticker_text(titles, args.max_chars)
                    print(f"  -> {text[:80]}{'…' if len(text) > 80 else ''}")
                    push(dev_holder, COLOR_ORANGE + normalize_for_sign(name), mode="HOLD")
                    time.sleep(args.intro_seconds)
                    push(dev_holder, text, mode="ROTATE")
                    # Wait for roughly one full scroll pass: the text must
                    # travel its own length plus the display width.
                    scroll_sec = (len(text) + SIGN_WIDTH_CHARS) / args.scroll_speed
                    scroll_sec += SCROLL_PADDING_SEC
                    print(f"  scrolling ~{scroll_sec:.0f}s before next feed")
                    time.sleep(scroll_sec)
            except Exception as e:
                print(f"  ! {name} refresh failed: {e}", file=sys.stderr)
                time.sleep(5)  # short pause on error so we don't busy-loop

            if args.once:
                return
            idx = (idx + 1) % len(feeds)
    except KeyboardInterrupt:
        print("\nStopping.")
    finally:
        import usb.util
        usb.util.dispose_resources(dev_holder[0])


if __name__ == "__main__":
    main()
