"""Install or remove a LaunchAgent so the menu bar ticker auto-launches at
login and restarts if it ever quits.

Usage:
    python install_login_item.py             # install (default)
    python install_login_item.py --install
    python install_login_item.py --uninstall

The agent runs this same Python interpreter on ticker_app.py. Logs go to
~/Library/Logs/betabrite-ticker/.
"""

import argparse
import os
import plistlib
import shutil
import subprocess
import sys

LABEL = "com.betabrite.ticker"
HERE = os.path.dirname(os.path.abspath(__file__))
APP_SCRIPT = os.path.join(HERE, "ticker_app.py")
PYTHON = sys.executable
HOME = os.path.expanduser("~")
AGENT_DIR = os.path.join(HOME, "Library", "LaunchAgents")
AGENT_PATH = os.path.join(AGENT_DIR, f"{LABEL}.plist")
LOG_DIR = os.path.join(HOME, "Library", "Logs", "betabrite-ticker")
DOMAIN = f"gui/{os.getuid()}"


def build_plist() -> dict:
    return {
        "Label": LABEL,
        "ProgramArguments": [PYTHON, APP_SCRIPT],
        "WorkingDirectory": HERE,
        "RunAtLoad": True,
        "KeepAlive": True,
        "StandardOutPath": os.path.join(LOG_DIR, "stdout.log"),
        "StandardErrorPath": os.path.join(LOG_DIR, "stderr.log"),
    }


def _run(cmd: list, check: bool = False):
    return subprocess.run(cmd, check=check,
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def install() -> None:
    if not os.path.exists(APP_SCRIPT):
        sys.exit(f"error: {APP_SCRIPT} not found")
    os.makedirs(AGENT_DIR, exist_ok=True)
    os.makedirs(LOG_DIR, exist_ok=True)
    with open(AGENT_PATH, "wb") as f:
        plistlib.dump(build_plist(), f)
    _run(["launchctl", "bootout", DOMAIN, AGENT_PATH])
    if not _run(["launchctl", "bootstrap", DOMAIN, AGENT_PATH]).returncode == 0:
        _run(["launchctl", "load", AGENT_PATH])
    print(f"Installed {AGENT_PATH}")
    print(f"  runs : {PYTHON}")
    print(f"         {APP_SCRIPT}")
    print(f"  logs : {LOG_DIR}")
    print("The ticker is now running and will auto-launch at login.")


def uninstall() -> None:
    _run(["launchctl", "bootout", DOMAIN, AGENT_PATH])
    _run(["launchctl", "unload", AGENT_PATH])
    if os.path.exists(AGENT_PATH):
        os.remove(AGENT_PATH)
    print(f"Removed {AGENT_PATH}")


def main() -> None:
    p = argparse.ArgumentParser(description=(
        "Auto-launch the Betabrite menu bar ticker at login."))
    g = p.add_mutually_exclusive_group()
    g.add_argument("--install", action="store_true", help="install and start (default)")
    g.add_argument("--uninstall", action="store_true", help="stop and remove")
    args = p.parse_args()
    uninstall() if args.uninstall else install()


if __name__ == "__main__":
    main()