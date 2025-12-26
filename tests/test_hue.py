from __future__ import annotations

import pytest

from coco_attention.hue import HueClient, discover_bridges


class DummyResponse:
    def __init__(self, payload, status: int = 200) -> None:
        self._payload = payload
        self.status_code = status

    def json(self):
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def test_list_lights(monkeypatch) -> None:
    def fake_get(url, timeout=5):
        assert url == "http://bridge/api/user/lights"
        return DummyResponse({"1": {"name": "Desk"}, "2": {"name": "Hall"}})

    monkeypatch.setattr("coco_attention.hue.requests.get", fake_get)
    client = HueClient("bridge", "user")

    assert client.list_lights() == {"1": "Desk", "2": "Hall"}


def test_get_light_state(monkeypatch) -> None:
    def fake_get(url, timeout=5):
        assert url == "http://bridge/api/user/lights/9"
        return DummyResponse({"state": {"on": True, "bri": 120, "hue": 500, "sat": 200}})

    monkeypatch.setattr("coco_attention.hue.requests.get", fake_get)
    client = HueClient("bridge", "user")

    state = client.get_light_state("9")
    assert state.on is True
    assert state.bri == 120
    assert state.hue == 500
    assert state.sat == 200


def test_set_light_state(monkeypatch) -> None:
    captured = {}

    def fake_put(url, json, timeout=5):
        captured["url"] = url
        captured["json"] = json
        return DummyResponse({})

    monkeypatch.setattr("coco_attention.hue.requests.put", fake_put)
    client = HueClient("bridge", "user")

    client.set_light_state("4", {"on": True})

    assert captured["url"] == "http://bridge/api/user/lights/4/state"
    assert captured["json"] == {"on": True}


def test_register(monkeypatch) -> None:
    def fake_post(url, json, timeout=5):
        assert url == "http://bridge/api"
        assert json["devicetype"] == "coco_attention#cli"
        return DummyResponse([{"success": {"username": "abc123"}}])

    monkeypatch.setattr("coco_attention.hue.requests.post", fake_post)
    client = HueClient("bridge", "user")

    assert client.register() == "abc123"


def test_register_error(monkeypatch) -> None:
    def fake_post(url, json, timeout=5):
        return DummyResponse([{"error": {"type": 101}}])

    monkeypatch.setattr("coco_attention.hue.requests.post", fake_post)
    client = HueClient("bridge", "user")

    with pytest.raises(RuntimeError):
        client.register()


def test_discover_bridges(monkeypatch) -> None:
    def fake_get(url, timeout=5):
        return DummyResponse([{"id": "bridge1"}])

    monkeypatch.setattr("coco_attention.hue.requests.get", fake_get)

    assert discover_bridges() == [{"id": "bridge1"}]


def test_discover_bridges_invalid(monkeypatch) -> None:
    def fake_get(url, timeout=5):
        return DummyResponse({"id": "bridge1"})

    monkeypatch.setattr("coco_attention.hue.requests.get", fake_get)

    with pytest.raises(RuntimeError):
        discover_bridges()
