"""One-shot helper: tell the Betabrite to allocate a big TEXT file A.

Run this once (or whenever you want to change the allocation). It wipes
the sign's memory configuration and sets file A to the given size.
"""

import argparse
import usb.util

import betabrite_usb as bb


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--size", type=lambda s: int(s, 0), default=4096,
                   help="Bytes to allocate for file A (default 4096, max 65535)")
    args = p.parse_args()

    dev = bb.open_display()
    try:
        bb.send(dev, bb.build_memory_config_packet(size=args.size))
        print(f"Allocated {args.size} bytes for file A.")
        # Push a short message so something is showing afterwards.
        bb.send(dev, bb.build_packet("READY", mode="HOLD"))
    finally:
        usb.util.dispose_resources(dev)


if __name__ == "__main__":
    main()
