from __future__ import annotations

from coco_attention.config import (
    Config,
    LastState,
    LightState,
    load_config,
    load_last_state,
    save_config,
    save_last_state,
)


def test_save_and_load_config(tmp_path) -> None:
    path = tmp_path / "config.json"
    config = Config(bridge_ip="10.0.0.5", username="user", light_id="3")

    save_config(path, config)
    loaded = load_config(path)

    assert loaded == config


def test_save_and_load_last_state(tmp_path) -> None:
    path = tmp_path / "last_state.json"
    state = LastState(
        lights={
            "3": LightState(light_id="3", on=True, bri=120, hue=10000, sat=200),
            "7": LightState(light_id="7", on=False, bri=10, hue=2000, sat=30),
        }
    )

    save_last_state(path, state)
    loaded = load_last_state(path)

    assert loaded == state


def test_load_legacy_last_state(tmp_path) -> None:
    path = tmp_path / "legacy.json"
    path.write_text(
        """
        {
          "light_id": "5",
          "on": true,
          "bri": 210,
          "hue": 5000,
          "sat": 100
        }
        """.strip()
    )

    loaded = load_last_state(path)

    assert loaded.lights["5"].light_id == "5"
    assert loaded.lights["5"].on is True
