from __future__ import annotations

import argparse
import socket
import time
from pathlib import Path

import requests

from .config import (
    DEFAULT_CONFIG_PATH,
    Config,
    LastState,
    load_config,
    load_last_state,
    save_config,
    save_last_state,
    last_state_path,
)
from .hue import HueClient, discover_bridges


RED_ALERT = {"on": True, "bri": 254, "hue": 0, "sat": 254}
PRESETS = {
    "red": {"on": True, "bri": 254, "hue": 0, "sat": 254},
    "blue": {"on": True, "bri": 200, "hue": 46920, "sat": 254},
    "green": {"on": True, "bri": 200, "hue": 25500, "sat": 254},
    "warm": {"on": True, "bri": 200, "hue": 8000, "sat": 200},
    "cool": {"on": True, "bri": 200, "hue": 38000, "sat": 150},
}


def _config_path_from_args(args: argparse.Namespace) -> Path:
    return Path(args.config).expanduser() if args.config else DEFAULT_CONFIG_PATH


def cmd_register(args: argparse.Namespace) -> None:
    client = HueClient(args.bridge_ip, username="")
    username = client.register()
    print(username)


def cmd_config(args: argparse.Namespace) -> None:
    config_path = _config_path_from_args(args)
    cfg = Config(
        bridge_ip=args.bridge_ip,
        username=args.username,
        light_id=args.light_id,
    )
    save_config(config_path, cfg)
    print(f"Saved config to {config_path}")


def _prompt_choice(prompt: str, options: list[str]) -> int:
    while True:
        print(prompt)
        for idx, option in enumerate(options, start=1):
            print(f"{idx}) {option}")
        choice = input("Select a number: ").strip()
        if choice.isdigit():
            value = int(choice)
            if 1 <= value <= len(options):
                return value - 1
        print("Invalid choice, try again.")


def _setup_config(
    config_path: Path,
    bridge_ip: str | None = None,
    username: str | None = None,
    light_id: str | None = None,
    non_interactive: bool = False,
) -> Config:
    if not bridge_ip:
        bridges = discover_bridges()
        if not bridges:
            raise SystemExit("No Hue bridges found on the network.")
        if len(bridges) == 1:
            bridge_ip = bridges[0].get("internalipaddress", "")
        else:
            if non_interactive:
                raise SystemExit(
                    "Multiple Hue bridges found. Pass --bridge-ip or run setup interactively."
                )
            labels = [
                f"{b.get('internalipaddress', '')} ({b.get('id', 'unknown')})"
                for b in bridges
            ]
            idx = _prompt_choice("Multiple Hue bridges found:", labels)
            bridge_ip = bridges[idx].get("internalipaddress", "")
        if not bridge_ip:
            raise SystemExit("Could not determine Hue bridge IP.")

    if not username:
        if non_interactive:
            raise SystemExit(
                "Username is required in non-interactive mode. "
                "Run setup interactively or provide --username."
            )
        print("Press the Hue bridge button, then press Enter to register.")
        input()
        client = HueClient(bridge_ip, username="")
        try:
            username = client.register()
        except RuntimeError as exc:
            raise SystemExit(f"Registration failed. {exc}")

    client = HueClient(bridge_ip, username)
    if not light_id:
        lights = client.list_lights()
        if not lights:
            raise SystemExit("No lights found on the Hue bridge.")
        light_ids = list(lights.keys())
        if len(light_ids) == 1:
            light_id = light_ids[0]
        else:
            if non_interactive:
                raise SystemExit(
                    "Multiple lights found. Pass --light-id or run setup interactively."
                )
            labels = [f"{light_id}: {lights[light_id]}" for light_id in light_ids]
            idx = _prompt_choice("Choose a light to control:", labels)
            light_id = light_ids[idx]

    cfg = Config(bridge_ip=bridge_ip, username=username, light_id=light_id)
    save_config(config_path, cfg)
    print(f"Saved config to {config_path}")
    return cfg


def _ensure_config(config_path: Path, non_interactive: bool = False) -> Config:
    if config_path.exists():
        return load_config(config_path)
    if non_interactive:
        raise SystemExit(
            "No config found. Run `coco-attention setup` or provide --config."
        )
    print("No config found; starting setup.")
    return _setup_config(config_path)


def cmd_list_lights(args: argparse.Namespace) -> None:
    if args.bridge_ip and args.username:
        client = HueClient(args.bridge_ip, args.username)
    else:
        config_path = _config_path_from_args(args)
        if not config_path.exists():
            raise SystemExit("No config found. Run setup first.")
        cfg = load_config(config_path)
        client = HueClient(cfg.bridge_ip, cfg.username)

    lights = client.list_lights()
    for light_id, name in lights.items():
        print(f"{light_id}\t{name}")


def cmd_alert(args: argparse.Namespace) -> None:
    config_path = _config_path_from_args(args)
    cfg = _ensure_config(config_path, non_interactive=args.non_interactive)
    client = HueClient(cfg.bridge_ip, cfg.username)

    lights_ids = [cfg.light_id]
    state = LastState(lights={})

    if args.urgent:
        lights_ids.append("3")  # Armoire light

    for light_id in lights_ids:
        state.lights[light_id] = client.get_light_state(light_id)
        state.lights[light_id].light_id = light_id
    print(state)
    save_last_state(last_state_path(config_path), state)

    try:
        _pulse_alert(client, lights_ids, period=args.period, low_bri=args.low_bri)
    except KeyboardInterrupt:
        cmd_restore(args)
        print("Alert stopped and light restored.")


def cmd_restore(args: argparse.Namespace) -> None:
    config_path = _config_path_from_args(args)
    cfg = _ensure_config(config_path, non_interactive=args.non_interactive)
    state_path = last_state_path(config_path)
    if not state_path.exists():
        raise SystemExit("No saved state found. Run alert or set first.")

    last_state = load_last_state(state_path)
    if not last_state.lights:
        raise SystemExit("No saved state found. Run alert or set first.")
    client = HueClient(cfg.bridge_ip, cfg.username)
    for saved_light_id, state in last_state.lights.items():
        light_id = state.light_id or saved_light_id or cfg.light_id
        payload = {
            key: value
            for key, value in state.__dict__.items()
            if key != "light_id" and value is not None
        }
        if not payload:
            continue
        client.set_light_state(light_id, payload)
    print("Light state restored.")


def cmd_setup(args: argparse.Namespace) -> None:
    config_path = _config_path_from_args(args)
    _setup_config(
        config_path,
        bridge_ip=args.bridge_ip,
        username=args.username,
        light_id=args.light_id,
        non_interactive=args.non_interactive,
    )


def cmd_set(args: argparse.Namespace) -> None:
    config_path = _config_path_from_args(args)
    cfg = _ensure_config(config_path, non_interactive=args.non_interactive)
    client = HueClient(cfg.bridge_ip, cfg.username)
    light_id = args.light_id or cfg.light_id

    state = client.get_light_state(light_id)
    state.light_id = light_id
    save_last_state(last_state_path(config_path), LastState(lights={light_id: state}))

    payload: dict = {}
    if args.preset:
        payload.update(PRESETS[args.preset])
    if args.on is not None:
        payload["on"] = args.on
    if args.bri is not None:
        payload["bri"] = args.bri
    if args.hue is not None:
        payload["hue"] = args.hue
    if args.sat is not None:
        payload["sat"] = args.sat

    if not payload:
        raise SystemExit("No state provided. Use --on/--off, --bri, --hue, or --sat.")

    client.set_light_state(light_id, payload)
    print(f"Light {light_id} updated.")


def _pulse_alert(client: HueClient, light_ids: list[str], period: float, low_bri: int) -> None:
    if period <= 0:
        raise SystemExit("--period must be greater than 0.")
    half_period = period / 8
    transition_time = max(1, int(half_period * 10))
    high = {**RED_ALERT, "transitiontime": transition_time}
    low = {**RED_ALERT, "bri": low_bri, "transitiontime": transition_time}

    def pulse_once(light_id: str) -> None:
        client.set_light_state(light_id, high)
        time.sleep(half_period)
        client.set_light_state(light_id, low)
        time.sleep(half_period)

    while True:
        for light_id in light_ids:
            pulse_once(light_id)

def _check_tcp(ip: str, port: int = 80, timeout: float = 2.0) -> str:
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            return "reachable"
    except OSError as exc:
        return f"unreachable ({exc})"


def _check_http(ip: str, timeout: float = 2.0) -> str:
    try:
        resp = requests.get(f"http://{ip}/api/config", timeout=timeout)
        return f"http {resp.status_code}"
    except requests.RequestException as exc:
        return f"http error ({exc})"


def cmd_diagnose(args: argparse.Namespace) -> None:
    local_ip = _local_ip()
    if local_ip:
        print(f"Local IP: {local_ip}")
    else:
        print("Local IP: unknown")

    print("Discovering Hue bridges...")
    try:
        bridges = discover_bridges()
    except requests.RequestException as exc:
        raise SystemExit(f"Discovery failed: {exc}")

    if not bridges:
        raise SystemExit("No Hue bridges found via discovery.")

    for bridge in bridges:
        ip = bridge.get("internalipaddress", "")
        bridge_id = bridge.get("id", "unknown")
        print(f"- Bridge {bridge_id} at {ip}")
        if not ip:
            print("  tcp: unknown (missing IP)")
            continue
        if local_ip:
            if _same_subnet(local_ip, ip):
                print("  subnet: same")
            else:
                print("  subnet: different")
        print(f"  tcp: {_check_tcp(ip)}")
        print(f"  http: {_check_http(ip)}")

    print("If tcp is unreachable, your device cannot reach the bridge on the LAN.")
    print("Common causes: guest Wi-Fi, AP isolation, different subnet, or VPN.")


def _local_ip() -> str | None:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            return sock.getsockname()[0]
    except OSError:
        return None


def _same_subnet(ip_a: str, ip_b: str) -> bool:
    parts_a = ip_a.split(".")
    parts_b = ip_b.split(".")
    if len(parts_a) != 4 or len(parts_b) != 4:
        return False
    return parts_a[:3] == parts_b[:3]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="coco-attention",
        description="Set a Hue light to red as an attention alert.",
    )
    parser.add_argument(
        "--config",
        help="Path to config JSON (default: ~/.config/coco_attention/config.json)",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    p_register = sub.add_parser("register", help="Register with the Hue bridge")
    p_register.add_argument("--bridge-ip", required=True)
    p_register.set_defaults(func=cmd_register)

    p_config = sub.add_parser("config", help="Save bridge credentials")
    p_config.add_argument("--bridge-ip", required=True)
    p_config.add_argument("--username", required=True)
    p_config.add_argument("--light-id", required=True)
    p_config.set_defaults(func=cmd_config)

    p_setup = sub.add_parser(
        "setup",
        help="Discover bridge, register, and save config interactively",
    )
    p_setup.add_argument("--bridge-ip")
    p_setup.add_argument("--username")
    p_setup.add_argument("--light-id")
    p_setup.add_argument(
        "--non-interactive",
        action="store_true",
        help="Fail instead of prompting; requires explicit values",
    )
    p_setup.set_defaults(func=cmd_setup)

    p_diag = sub.add_parser("diagnose", help="Check Hue bridge reachability")
    p_diag.set_defaults(func=cmd_diagnose)

    p_lights = sub.add_parser("list-lights", help="List light IDs and names")
    p_lights.add_argument("--bridge-ip")
    p_lights.add_argument("--username")
    p_lights.set_defaults(func=cmd_list_lights)

    p_alert = sub.add_parser("alert", help="Set the light to red")
    p_alert.add_argument(
        "--period",
        type=float,
        default=2.0,
        help="Seconds per pulse cycle (default: 2.0)",
    )
    p_alert.add_argument(
        "--low-bri",
        type=int,
        default=80,
        help="Low brightness level during pulse (default: 80)",
    )
    p_alert.add_argument(
        "--non-interactive",
        action="store_true",
        help="Fail instead of prompting when config is missing",
    )
    p_alert.add_argument(
        "--urgent",
        action="store_true",
        help="Alternate between the red PC light and the armoire light",
    )
    p_alert.set_defaults(func=cmd_alert)

    p_restore = sub.add_parser("restore", help="Restore the last captured state")
    p_restore.add_argument(
        "--non-interactive",
        action="store_true",
        help="Fail instead of prompting when config is missing",
    )
    p_restore.set_defaults(func=cmd_restore)

    p_set = sub.add_parser("set", help="Set any light state and save previous state")
    p_set.add_argument("--light-id", help="Light ID to control (defaults to config)")
    p_set.add_argument(
        "--preset",
        choices=sorted(PRESETS.keys()),
        help="Apply a color preset",
    )
    p_set.add_argument(
        "--on",
        dest="on",
        action="store_const",
        const=True,
        default=None,
        help="Turn the light on",
    )
    p_set.add_argument(
        "--off",
        dest="on",
        action="store_const",
        const=False,
        default=None,
        help="Turn the light off",
    )
    p_set.add_argument("--bri", type=int, help="Brightness 1-254")
    p_set.add_argument("--hue", type=int, help="Hue 0-65535")
    p_set.add_argument("--sat", type=int, help="Saturation 0-254")
    p_set.add_argument(
        "--non-interactive",
        action="store_true",
        help="Fail instead of prompting when config is missing",
    )
    p_set.set_defaults(func=cmd_set)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)
