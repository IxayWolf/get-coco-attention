from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional


DEFAULT_CONFIG_PATH = Path.home() / ".config" / "coco_attention" / "config.json"


@dataclass
class Config:
    bridge_ip: str
    username: str
    light_id: str


@dataclass
class LastState:
    lights: dict[str, LightState]  # Mapping of light IDs to their last known state

@dataclass
class LightState:
    light_id: Optional[str] = None
    on: Optional[bool] = None
    bri: Optional[int] = None
    hue: Optional[int] = None
    sat: Optional[int] = None


def load_config(path: Path) -> Config:
    data = json.loads(path.read_text())
    return Config(
        bridge_ip=data["bridge_ip"],
        username=data["username"],
        light_id=str(data["light_id"]),
    )


def save_config(path: Path, config: Config) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "bridge_ip": config.bridge_ip,
                "username": config.username,
                "light_id": config.light_id,
            },
            indent=2,
        )
    )


def last_state_path(config_path: Path) -> Path:
    return config_path.with_name("last_state.json")


def save_last_state(path: Path, state: LastState) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(state), indent=2))


def load_last_state(path: Path) -> LastState:
    data = json.loads(path.read_text())
    if "lights" in data:
        lights: dict[str, LightState] = {}
        for light_id, light_data in data.get("lights", {}).items():
            if light_data.get("light_id") is None:
                light_data["light_id"] = light_id
            lights[light_id] = LightState(**light_data)
        return LastState(lights=lights)
    light_id = data.get("light_id")
    return LastState(lights={light_id or "": LightState(**data)})
