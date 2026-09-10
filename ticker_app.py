"""Betabrite Ticker — macOS menu bar app.

Watches for the Betabrite USB display and auto-starts/stops the RSS news
ticker as the sign is plugged in and out. Clicking the menu bar icon shows
live status, an auto-run toggle, manual start/stop, and quit.

Run:
    python ticker_app.py

Requires: rumps (pip install rumps) — pulls in PyObjC for the menu bar.
Reuses the existing USB driver and ticker helpers; no protocol code is
duplicated here.
"""

import threading
import time

import rumps
import usb.core
import usb.util

import betabrite_usb as bb
from news_ticker import (
    DEFAULT_FEEDS,
    DEFAULT_INTRO_SECONDS,
    DEFAULT_MAX_CHARS,
    DEFAULT_MAX_ITEMS,
    DEFAULT_SCROLL_CHARS_PER_SEC,
    SCROLL_PADDING_SEC,
    SIGN_WIDTH_CHARS,
    COLOR_ORANGE,
    build_ticker_text,
    fetch_headlines,
    normalize_for_sign,
    push,
)

POLL_SECONDS = 2.0
UI_REFRESH_SECONDS = 0.5


def find_display():
    """Return the Betabrite USB device if connected, else None.

    Only enumerates the device tree — it does not claim the interface, so it
    is safe to call repeatedly even while the ticker holds the device.
    """
    try:
        return usb.core.find(idVendor=bb.VID, idProduct=bb.PID)
    except usb.core.USBError:
        return None


class TickerApp(rumps.App):
    def __init__(self):
        super().__init__("📟", quit_button=None)

        # Menu items — touched by the main thread only.
        self.status = rumps.MenuItem("○ No display")
        self.auto_item = rumps.MenuItem("Auto-run on connect", callback=self._toggle_auto)
        self.start_item = rumps.MenuItem("Start ticker", callback=self._manual_start)
        self.stop_item = rumps.MenuItem("Stop ticker", callback=self._manual_stop)
        self.quit_item = rumps.MenuItem("Quit", callback=self._quit)
        self.menu = [self.status, None, self.auto_item, self.start_item,
                     self.stop_item, None, self.quit_item]

        # State. Worker threads mutate these only under self._lock and never
        # touch the Cocoa menu items; the main-thread timer does that sync.
        self._lock = threading.Lock()
        self._auto = True
        self._running = False
        self._starting = False
        self._device_present = False
        self._error = None
        self._ticker_thread = None
        self._dev_holder = None
        self._stop_event = threading.Event()

        threading.Thread(target=self._watch_loop, daemon=True).start()
        self._timer = rumps.Timer(self._refresh_ui, UI_REFRESH_SECONDS)
        self._timer.start()
        self._refresh_ui()

    def _toggle_auto(self, _):
        with self._lock:
            self._auto = not self._auto

    def _manual_start(self, _):
        with self._lock:
            self._auto = True
        self._start_ticker()

    def _manual_stop(self, _):
        with self._lock:
            self._auto = False
        self._stop_ticker()

    def _quit(self, _):
        self._stop_ticker()
        rumps.quit_application()

    def _start_ticker(self):
        """Start the ticker. Never blocks the caller — the USB open runs in a
        short-lived worker so the UI thread is never held up."""
        with self._lock:
            if self._running or self._starting:
                return
            self._starting = True
        threading.Thread(target=self._start_worker, daemon=True).start()

    def _start_worker(self):
        try:
            with self._lock:
                if self._running:
                    return
            try:
                dev = bb.open_display()
            except Exception as e:
                with self._lock:
                    self._error = f"connect failed: {e}"
                return
            with self._lock:
                self._dev_holder = [dev]
                self._stop_event.clear()
                self._error = None
                self._running = True
                self._ticker_thread = threading.Thread(
                    target=self._ticker_loop, args=(self._dev_holder,), daemon=True
                )
                self._ticker_thread.start()
        finally:
            with self._lock:
                self._starting = False

    def _stop_ticker(self):
        with self._lock:
            if not self._running:
                return
            self._stop_event.set()
            thread = self._ticker_thread
        # The loop releases the USB handle in its own finally, so a bounded
        # join here is safe.
        if thread is not None:
            thread.join(timeout=4)
        with self._lock:
            self._running = False
            self._ticker_thread = None

    def _sleep(self, seconds):
        """Interruptible sleep; returns True if a stop was requested."""
        return self._stop_event.wait(timeout=seconds)

    def _ticker_loop(self, dev_holder):
        feeds = list(DEFAULT_FEEDS)
        idx = 0
        try:
            while not self._stop_event.is_set():
                name, url = feeds[idx]
                try:
                    titles = fetch_headlines(url, DEFAULT_MAX_ITEMS)
                    if titles:
                        text = build_ticker_text(titles, DEFAULT_MAX_CHARS)
                        push(dev_holder, COLOR_ORANGE + normalize_for_sign(name), mode="HOLD")
                        if self._sleep(DEFAULT_INTRO_SECONDS):
                            break
                        push(dev_holder, text, mode="ROTATE")
                        # One full scroll pass = text length + display width.
                        scroll = (len(text) + SIGN_WIDTH_CHARS) / DEFAULT_SCROLL_CHARS_PER_SEC
                        if self._sleep(scroll + SCROLL_PADDING_SEC):
                            break
                except Exception as e:
                    if find_display() is None:
                        with self._lock:
                            self._error = "display unplugged"
                        self._stop_event.set()
                        break
                    with self._lock:
                        self._error = f"{name} refresh failed: {e}"
                    if self._sleep(5):
                        break
                idx = (idx + 1) % len(feeds)
        finally:
            try:
                usb.util.dispose_resources(dev_holder[0])
            except Exception:
                pass

    def _watch_loop(self):
        while True:
            present = find_display() is not None
            with self._lock:
                self._device_present = present
                auto = self._auto
                running = self._running
            if present and auto and not running:
                self._start_ticker()
            elif not present and running:
                self._stop_ticker()
            time.sleep(POLL_SECONDS)

    def _set_enabled(self, item, enabled):
        item._menuitem.setEnabled_(enabled)

    def _refresh_ui(self, sender=None):
        with self._lock:
            running = self._running
            present = self._device_present
            error = self._error
            auto = self._auto

        if running:
            self.status.title = "● Ticker running"
        elif error:
            self.status.title = f"⚠ {error}"
        elif present:
            self.status.title = "○ Display connected (idle)"
        else:
            self.status.title = "○ No display"

        self.auto_item.state = 1 if auto else 0
        self._set_enabled(self.start_item, not running)
        self._set_enabled(self.stop_item, running)


def main():
    TickerApp().run()


if __name__ == "__main__":
    main()