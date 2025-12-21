# Coco Attention

A small Python CLI that turns a Hue light red to get attention.

## What it does
- Stores Hue bridge connection details in a local config file.
- Lists your lights so you can find the right light ID.
- Sends a command to set a specific light to a red glow.
- Restores the previous light state.

## Quick Start
```bash
uv sync
uv run coco-attention setup
uv run coco-attention alert
```

## Setup (uv)
1) Sync dependencies:

```bash
uv sync
```

2) Run the interactive setup (auto-discovers bridge IP, registers, and lets you choose a light):

```bash
uv run coco-attention setup
```

The setup will ask you to press the Hue bridge button to register a username.

3) For non-interactive usage (no prompts), provide everything explicitly:

```bash
uv run coco-attention setup --non-interactive --bridge-ip <BRIDGE_IP> --username <USERNAME> --light-id <LIGHT_ID>
```

4) If you want to be explicit but still interactive, you can provide details manually:

- Find your Hue bridge IP (check your router or Hue app).
- Register a username (press the Hue bridge button first):

```bash
uv run coco-attention register --bridge-ip <BRIDGE_IP>
```

5) List your lights to find the light ID:

```bash
uv run coco-attention list-lights --bridge-ip <BRIDGE_IP> --username <USERNAME>
```

6) Save your config (bridge IP, username, light ID):

```bash
uv run coco-attention config --bridge-ip <BRIDGE_IP> --username <USERNAME> --light-id <LIGHT_ID>
```

The config is saved at `~/.config/coco_attention/config.json` by default.

## Usage
Show your lights (requires config or bridge + username):

```bash
uv run coco-attention list-lights
```

Turn the light red (continuous pulsing, saves the previous state automatically):

```bash
uv run coco-attention alert
```

Press Ctrl+C to stop the pulse and automatically restore the previous state.

Tune the pulse speed or glow level:

```bash
uv run coco-attention alert --period 1.5 --low-bri 60
```

If no config exists yet, `alert` will walk you through setup before turning the light red.

For headless use, pass `--non-interactive` so it fails instead of prompting:

```bash
uv run coco-attention alert --non-interactive
```

Set any light state (also saves previous state automatically):

```bash
uv run coco-attention set --light-id 3 --on --bri 200 --hue 10000 --sat 200
```

Use a preset color:

```bash
uv run coco-attention set --light-id 3 --preset blue
```

Available presets: red, blue, green, warm, cool.

Check bridge reachability:

```bash
uv run coco-attention diagnose
```

Restore the previous state:

```bash
uv run coco-attention restore
```

You can also point at a custom config file:

```bash
uv run coco-attention alert --config /path/to/config.json
```

## Notes
- Hue light IDs can be seen in the Hue API (GET `/api/<username>/lights`).
- This tool is intentionally simple and uses the Hue local API.
