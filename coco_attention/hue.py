from __future__ import annotations

import requests

from .config import LightState


DISCOVERY_URL = "https://discovery.meethue.com/"


class HueClient:
    def __init__(self, bridge_ip: str, username: str) -> None:
        self.bridge_ip = bridge_ip
        self.username = username

    def _url(self, path: str) -> str:
        return f"http://{self.bridge_ip}/api/{self.username}{path}"

    def get_light_state(self, light_id: str) -> LightState:
        resp = requests.get(self._url(f"/lights/{light_id}"), timeout=5)
        resp.raise_for_status()
        data = resp.json()
        state = data.get("state", {})
        return LightState(
            on=state.get("on"),
            bri=state.get("bri"),
            hue=state.get("hue"),
            sat=state.get("sat"),
        )

    def list_lights(self) -> dict[str, str]:
        resp = requests.get(self._url("/lights"), timeout=5)
        resp.raise_for_status()
        data = resp.json()
        return {light_id: info.get("name", "") for light_id, info in data.items()}

    def set_light_state(self, light_id: str, payload: dict) -> None:
        resp = requests.put(
            self._url(f"/lights/{light_id}/state"), json=payload, timeout=5
        )
        resp.raise_for_status()

    def register(self, devicetype: str = "coco_attention#cli") -> str:
        resp = requests.post(
            f"http://{self.bridge_ip}/api", json={"devicetype": devicetype}, timeout=5
        )
        resp.raise_for_status()
        data = resp.json()
        if not data or "error" in data[0]:
            raise RuntimeError(f"Registration failed: {data}")
        return data[0]["success"]["username"]


def discover_bridges() -> list[dict]:
    resp = requests.get(DISCOVERY_URL, timeout=5)
    resp.raise_for_status()
    data = resp.json()
    if not isinstance(data, list):
        raise RuntimeError("Unexpected response from Hue discovery service.")
    return data
