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
- For a new variant, copy an existing variant file and change `CONTAINER` and `DASHBOARD_PORT`.
- Prose documentation (Hermes toolsets, plugins and extras; container internet troubleshooting) lives in README.md.
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
- API key comes from the prompt or `LLAMA_API_KEY`; it is read and checked by the shared `read_api_key` (all agents): rejected if it contains `'`, `"`, `\`, a newline or CR (`check_api_key`), then `preflight()` runs. Hermes writes it to the container's `~/.hermes/.env.llama` (0600) and merges it into `.env`, never passed on a command line.
- Variant files must have unique `CONTAINER` and `DASHBOARD_PORT` across all `*/variants/`; `settings.py` enforces this and names the conflicting file.
- `CONTEXT_LENGTH` must equal llama-server's per-slot `n_ctx`; `preflight()` also checks `/models`.
- `DASHBOARD_UNIT` is load-bearing: Hermes restarts a user unit with exactly that name after `hermes update`.
- If stage 2 stops with an SSH host-key mismatch, clear the stale entry for the container IP: `ssh-keygen -R <container-ip>`.

## ZeroClaw gotchas

- Defaults in `zeroclaw/defaults.py`: `RISK_LEVEL="supervised"`, `AUTO_APPROVE=["shell", "file_read", "file_write", "file_edit", "glob_search", "content_search", "memory_recall", "memory_store"]`, `ALLOWED_COMMANDS=["uname"]`, `WEB_SEARCH_ENABLED=False`; a variant reassigns them after `from zeroclaw.defaults import *`; `workspace_only` still confines writes to the workspace.
- The tool test (`zeroclaw agent`, runs `uname -a`) passes only because `shell` is auto-approved and `uname` is the only allow-listed command. The allow-list is strict: the shell tool runs only listed commands.
- API key lives in `~/.zeroclaw/config.toml` (0600). Its sha256 is in the `.deploy-settings` stamp, so a new key re-runs the apply step: `set_api_key_command` copies it from a staged `~/.zeroclaw/.api-key` (0600, removed after) into the provider table, then the service restarts. `config set` can't do this headless: it reads secrets only from a terminal. Deleting `config.toml` also drops browser pairings (`[gateway] paired_tokens`).
- `~/.zeroclaw/.deploy-settings` stamps applied settings. Delete it to force the next deploy to re-apply them and restart.
- Interrupted old-protocol deploys leave a `.deploy-settings` stamp claiming settings that were never applied; delete `~/.zeroclaw/.deploy-settings` once to force a clean re-apply.
- Pair a browser: `zeroclaw gateway get-paircode` in the container. Never set `require_pairing = false`.
- Logs: `journalctl --user -u zeroclaw`.
- A container previously deployed as Hermes on the same `DASHBOARD_PORT` still has `hermes-dashboard` holding the port; run `lxc delete --force <container>` before the first ZeroClaw deploy.
