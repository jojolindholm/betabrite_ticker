"""Drive a Betabrite display that exposes a native USB-BULK interface
(VID 0x8765 / PID 0x1234, "ADAPTIVE USB-BULK Device") using the Alpha
Sign Communications Protocol over USB bulk transfers.

Requires: pyusb, libusb (brew install libusb).
"""

import sys
import usb.core
import usb.util

VID = 0x8765
PID = 0x1234

NUL = b"\x00"
SOH = b"\x01"
STX = b"\x02"
ETX = b"\x03"
EOT = b"\x04"
ESC = b"\x1B"

# Single-byte display mode codes from the Alpha Sign Protocol spec.
MODES = {
    "ROTATE":     b"a",
    "HOLD":       b"b",
    "FLASH":      b"c",
    "ROLL_UP":    b"e",
    "ROLL_DOWN":  b"f",
    "ROLL_LEFT":  b"g",
    "ROLL_RIGHT": b"h",
    "WIPE_UP":    b"i",
    "WIPE_DOWN":  b"j",
    "WIPE_LEFT":  b"k",
    "WIPE_RIGHT": b"l",
    "SCROLL":     b"m",
    "AUTO":       b"o",
    "TWINKLE":    b"n0",
    "SPARKLE":    b"n1",
    "SNOW":       b"n2",
    "INTERLOCK":  b"n3",
    "SWITCH":     b"n4",
    "SLIDE":      b"n5",
    "SPRAY":      b"n6",
    "STARBURST":  b"n7",
    "WELCOME":    b"n8",
}


def build_memory_config_packet(file_label: bytes = b"A", size: int = 0x1000) -> bytes:
    """Allocate `size` bytes for a TEXT file under `file_label`.

    NOTE: Set Memory Configuration clears the sign's memory and re-allocates
    everything in the command. So we only configure file A here; any other
    files will be wiped. `size` is a hex word (max 0xFFFF = 65535 bytes per
    file, which is plenty for a ticker).
    """
    if not (1 <= size <= 0xFFFF):
        raise ValueError("size must fit in a 4-hex-digit word (1..65535)")
    entry = (
        file_label              # file label (e.g. b"A")
        + b"A"                  # file type: A = TEXT
        + b"U"                  # protection: U = unlocked
        + f"{size:04X}".encode()  # size as 4 hex digits
        + b"FF00"               # start/stop time: FF00 = always on
    )
    body = STX + b"E$" + entry
    return NUL * 5 + SOH + b"Z00" + body + EOT


def encode_text(message: str) -> bytes:
    """Encode message bytes for the sign. The Betabrite 1196 uses the
    CP437 (PC-8) codepage natively, so Swedish/European accented
    characters (å, ä, ö, é, ü, ß, ...) render correctly when encoded
    that way. Anything still un-encodable is dropped."""
    return message.encode("cp437", "ignore")


def build_packet(message: str, mode: str = "ROTATE", file_label: bytes = b"A") -> bytes:
    if mode not in MODES:
        raise ValueError(f"Unknown mode {mode!r}. Choose from {list(MODES)}")
    body = (
        STX
        + b"A" + file_label          # Write TEXT command + file label
        + ESC
        + b"0"                       # display position: middle line
        + MODES[mode]
        + encode_text(message)
    )
    return (
        NUL * 5                      # wakeup
        + SOH
        + b"Z00"                     # broadcast to all signs
        + body
        + EOT
    )


def open_display():
    dev = usb.core.find(idVendor=VID, idProduct=PID)
    if dev is None:
        raise RuntimeError(
            f"No Betabrite found (VID 0x{VID:04x} PID 0x{PID:04x}). "
            "Check power and USB cable."
        )
    # macOS does not claim vendor-specific interfaces, so no kernel-driver
    # detach is needed, but it's harmless on Linux.
    try:
        if dev.is_kernel_driver_active(0):
            dev.detach_kernel_driver(0)
    except (NotImplementedError, usb.core.USBError):
        pass
    # Only set the configuration if it isn't already active. On macOS,
    # re-setting a configuration that's already in effect fails with
    # ENOENT ("No such device") on subsequent runs.
    try:
        dev.get_active_configuration()
    except usb.core.USBError:
        dev.set_configuration()
    usb.util.claim_interface(dev, 0)
    return dev


def send(dev, packet: bytes) -> None:
    import time
    # Bulk OUT endpoint 0x02, 64-byte max packet — pyusb will chunk for us.
    try:
        dev.write(0x02, packet, timeout=2000)
    except usb.core.USBError:
        # Endpoint may be halted from a prior failed transfer. Clear it
        # and retry once before propagating.
        try:
            dev.clear_halt(0x02)
        except Exception:
            pass
        dev.write(0x02, packet, timeout=2000)
    # Give the sign time to ingest the message into file A before the
    # caller closes the USB handle. Without this, short-running scripts
    # tear down the connection mid-write and the message is dropped.
    time.sleep(0.5 + len(packet) / 2000.0)


def write_message(message: str, mode: str = "ROTATE") -> None:
    dev = open_display()
    try:
        send(dev, build_packet(message, mode))
    finally:
        usb.util.dispose_resources(dev)


def main(argv):
    msg = " ".join(argv[1:]) or "HELLO WORLD"
    print(f"Sending: {msg!r}")
    write_message(msg, mode="ROTATE")
    print("Sent.")


if __name__ == "__main__":
    main(sys.argv)
