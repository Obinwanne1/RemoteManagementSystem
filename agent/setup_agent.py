"""
Agent setup helper — configures config.ini for a new WiFi/LAN deployment.

Usage:
    python setup_agent.py <server_ip> <org_token>

Example:
    python setup_agent.py 192.168.1.100 a8b6ea9bceae8b9cff9e63c2519d3e306453c1325306c64d
"""
import sys
import configparser
from pathlib import Path


def setup(server_ip: str, org_token: str):
    config_path = Path(__file__).parent / "config.ini"
    if not config_path.exists():
        print(f"ERROR: config.ini not found at {config_path}")
        sys.exit(1)

    cfg = configparser.ConfigParser()
    cfg.read(config_path, encoding="utf-8")

    # Update API section
    if "api" not in cfg:
        cfg["api"] = {}
    cfg["api"]["url"] = f"http://{server_ip}:5000"
    cfg["api"]["org_token"] = org_token

    # Clear agent credentials to force re-registration on this machine
    if "agent" in cfg:
        cfg.remove_option("agent", "device_id")
        cfg.remove_option("agent", "agent_token")
        print("Cleared existing device_id and agent_token — will re-register on next start.")

    with open(config_path, "w", encoding="utf-8") as f:
        cfg.write(f)

    print(f"config.ini updated:")
    print(f"  url       = http://{server_ip}:5000")
    print(f"  org_token = {org_token[:8]}{'*' * (len(org_token) - 8)}")
    print()
    print("Now run:  python rmm_agent.py")
    print("The device will register and appear in the RMM dashboard within 60 seconds.")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)
    setup(server_ip=sys.argv[1], org_token=sys.argv[2])
