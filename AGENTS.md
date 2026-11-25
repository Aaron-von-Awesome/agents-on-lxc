# Agents on LXC

pyinfra 3.11.2 deploy that builds a Hermes, ZeroClaw or Pi agent container on an LXD host (Ubuntu LXD snap). Run from this directory on the LXD host.

## Deploy

```bash
uv sync
AGENT_VARIANT=hermes/<name> uv run pyinfra @local launch.py                 # stage 1: create/start container, SSH + dashboard proxy
AGENT_VARIANT=hermes/<name> uv run pyinfra inventory.py hermes/deploy.py    # stage 2: install/configure Hermes over SSH
AGENT_VARIANT=zeroclaw/<name> uv run pyinfra @local launch.py                # stage 1: same as hermes
AGENT_VARIANT=zeroclaw/<name> uv run pyinfra inventory.py zeroclaw/deploy.py   # stage 2: install/configure ZeroClaw over SSH
AGENT_VARIANT=pi/<name> uv run pyinfra @local launch.py                      # stage 1: same, no dashboard proxy
AGENT_VARIANT=pi/<name> uv run pyinfra inventory.py pi/deploy.py             # stage 2: install/configure Pi over SSH
```

- `pi/`: no dashboard; SSH in and run `pi`. `pi/deploy.py` owns `~/.pi/agent/models.json` and `settings.json` and rewrites them every run, so changes made inside Pi (`/model`, `/thinking` save, changelog state) are reset.
- `AGENT_VARIANT` is `<agent>/<name>` for `<agent>/variants/<name>.py`; `settings.py` loads it at import time. Required.
- Run stage 1 first: `inventory.py` reads the container IP from `lxc list` and fails if it is missing.
- Stage 1 also turns on LXD nesting (`security.nesting` plus the mknod/setxattr syscall intercepts, then a restart) and installs Helix (classic snap) and the Docker snap, with `SSH_USER` in the `docker` group. That group is effectively root in the container.
- Stage 1 runs on `@local` (the host) via `lxc exec`; stage 2 SSHes into the container.
- Variant `SSH_KEY_PATH` must have no passphrase: pyinfra cannot prompt for one.

## Tests

- `uv run pytest` (no LXD needed).
- `uv run pyright` typechecks (`[tool.pyright]`).
- `tests/conftest.py` defaults `AGENT_VARIANT=hermes/hermius-maximus`.
- `test_every_variant_loads` loads every `*/variants/*.py`.

## Gotchas

- Never pass pyinfra `--diff` to `hermes/deploy.py`, `zeroclaw/deploy.py` or `pi/deploy.py`: it raises rather than print the API-key file. Use `--dry` to preview.
- `--data chat_test=true` forces the chat test; it also auto-runs on a first install.
- API key comes from the prompt or `LLAMA_API_KEY`; it is rejected if it contains `'`, `"`, `\`, a newline or CR (shared `check_api_key`, all agents). Hermes writes it to the container's `~/.hermes/.env.llama` (0600) and merges it into `.env`, never passed on a command line.
- Variant files must have unique `CONTAINER` and `DASHBOARD_PORT` across all `*/variants/`; `settings.py` enforces this and names the conflicting file.
- `CONTEXT_LENGTH` must equal llama-server's per-slot `n_ctx`; `preflight()` also checks `/models`.
- `DASHBOARD_UNIT` is load-bearing: Hermes restarts a user unit with exactly that name after `hermes update`.

## ZeroClaw gotchas

- Defaults in `zeroclaw/defaults.py`: `RISK_LEVEL="supervised"`, `AUTO_APPROVE=["shell", "file_read", "file_write", "file_edit", "glob_search", "content_search", "memory_recall", "memory_store"]`, `ALLOWED_COMMANDS=["uname"]`, `WEB_SEARCH_ENABLED=False`.
- The tool test (`zeroclaw agent`, runs `uname -a`) passes only because `shell` is auto-approved and `uname` is the only allow-listed command. The allow-list is strict: the shell tool runs only listed commands.
- API key is written only on first run, into `~/.zeroclaw/config.toml` (0600). Rotate: delete `config.toml` (also drops browser pairings, which live in its `[gateway] paired_tokens`) or `zeroclaw config set` in the container, then `systemctl --user restart zeroclaw`.
- `~/.zeroclaw/.deploy-settings` stamps applied settings. Delete it to force the next deploy to re-apply them and restart.
- Pair a browser: `zeroclaw gateway get-paircode` in the container. Never set `require_pairing = false`.
- Logs: `journalctl --user -u zeroclaw`.
