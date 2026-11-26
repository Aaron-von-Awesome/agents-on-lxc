# Agents on LXC

Deploy Hermes Agent, ZeroClaw or Pi in an LXD container with pyinfra, using the Ubuntu LXD snap. Run on the LXD host, from this folder.

```bash
uv sync
AGENT_VARIANT=hermes/hermius-maximus uv run pyinfra @local launch.py
AGENT_VARIANT=hermes/hermius-maximus uv run pyinfra inventory.py hermes/deploy.py

AGENT_VARIANT=zeroclaw/zeroius-clawius uv run pyinfra @local launch.py
AGENT_VARIANT=zeroclaw/zeroius-clawius uv run pyinfra inventory.py zeroclaw/deploy.py

AGENT_VARIANT=pi/pious-agenticus uv run pyinfra @local launch.py
AGENT_VARIANT=pi/pious-agenticus uv run pyinfra inventory.py pi/deploy.py
```

## Deploy

- Run stage 1 first: `inventory.py` reads the container IP from `lxc list` and fails if it is missing.
- Stage 1 runs on `@local` (the host) via `lxc exec`; stage 2 SSHes into the container.
- Stage 1 creates/starts the container and opens SSH + dashboard proxy (variants with a dashboard), turns on LXD nesting (`security.nesting` plus the mknod/setxattr syscall intercepts, then a restart), and installs Helix (classic snap) and the Docker snap, with `SSH_USER` in the `docker` group. That group is effectively root in the container.
- `AGENT_VARIANT` is `<agent>/<name>` for `<agent>/variants/<name>.py`; `settings.py` loads it at import time. Required. For a new variant, copy an existing variant file and change `CONTAINER` and `DASHBOARD_PORT`.
- API key comes from the prompt or `LLAMA_API_KEY`; it is read and checked by the shared `read_api_key` (all agents): rejected if it contains `'`, `"`, `\`, a newline or CR (`check_api_key`), then `preflight()` runs. Hermes writes it to the container's `~/.hermes/.env.llama` (0600) and merges it into `.env`.
- Never pass pyinfra `--diff` to `hermes/deploy.py`, `zeroclaw/deploy.py` or `pi/deploy.py`: it raises rather than print the API-key file. Use `--dry` to preview.
- `--data chat_test=true` forces the chat test; it also auto-runs on a first install.
- Tests: `uv run pytest` (no LXD needed).
- If stage 2 stops with an SSH host-key mismatch, clear the stale entry for the container IP: `ssh-keygen -R <container-ip>`.

## Hermes

### Toolsets, plugins and extras

`hermes/defaults.py` sets these for every variant (`from hermes.defaults import *`); a variant can reassign one after that line. Stage 2 writes them to `config.yaml` on every run, so edits made in `hermes tools` or the dashboard are reset.

- `ENABLED_PLATFORM_TOOLSETS`: dict of platform → toolset allow-list, written as `platform_toolsets.<platform>` (today `cli` and `api_server`). A platform left out uses Hermes' broad default. Removing a platform from the dict does not delete its existing `config.yaml` entry.
- `DISABLED_TOOLSETS`: `agent.disabled_toolsets`, removed on every platform, even if a platform list includes them.
- `PLUGINS_ENABLED`: `plugins.enabled`. Third-party plugins load only when listed here.
- `PLUGINS_DISABLED`: `plugins.disabled`. Bundled backend and platform plugins load without being enabled, so this list keeps them off; it wins over `PLUGINS_ENABLED`. Hermes has no wildcard. After `hermes update`, list new bundled ones with:

  ```bash
  cd hermes-agent/plugins && grep -lE '^kind: (backend|platform)' */*/plugin.yaml | xargs -n1 dirname
  ```
- `PM_EXTRAS`: optional Hermes Python extras, installed with `hermes pm install --extra <name>`. Empty by default. Extras are install-wide, so every profile in the container gets them; `--profile` does not narrow that. Example: `PM_EXTRAS = ["anthropic"]` for a profile that uses the Anthropic provider. Removing a name does not uninstall it.
- `MOA_ENABLED`: Mixture of Agents. Stage 2 points the `default` preset at the variant's `MODEL` (advisor and aggregator), replacing Hermes' cloud-model default. `False` (default) turns the advisors off, so selecting the preset runs `MODEL` alone.
- `CLAUDE_CODE`: `True` runs the Claude Code installer (`CLAUDE_CODE_INSTALL_URL`) once, as `SSH_USER`, into `~/.local/bin/claude`. Off by default. Log in afterwards in the container with `claude`; turning it off does not uninstall it.

## ZeroClaw

- Defaults in `zeroclaw/defaults.py`: `RISK_LEVEL="supervised"`, `AUTO_APPROVE=["shell", "file_read", "file_write", "file_edit", "glob_search", "content_search", "memory_recall", "memory_store"]`, `ALLOWED_COMMANDS=["uname"]`, `WEB_SEARCH_ENABLED=False`; a variant reassigns them after `from zeroclaw.defaults import *`; `workspace_only` still confines writes to the workspace.
- The tool test (`zeroclaw agent`, runs `uname -a`) passes only because `shell` is auto-approved and `uname` is the only allow-listed command. The allow-list is strict: the shell tool runs only listed commands.
- The `docker` sandbox backend runs each shell command in a throwaway container (stage 1 installs the Docker snap and enables nesting); if Docker is missing, ZeroClaw logs a warning and runs unsandboxed. `SANDBOX_BACKEND = "none"` turns the OS sandbox off.
- API key lives in `~/.zeroclaw/config.toml` (0600). Its sha256 is in the `.deploy-settings` stamp, so a new key re-runs the apply step: `set_api_key_command` copies it from a staged `~/.zeroclaw/.api-key` (0600, removed after) into the provider table, then the service restarts. `config set` can't do this headless: it reads secrets only from a terminal. Deleting `config.toml` also drops browser pairings (`[gateway] paired_tokens`).
- `~/.zeroclaw/.deploy-settings` stamps applied settings. Delete it to force the next deploy to re-apply them and restart.
- Interrupted old-protocol deploys leave a `.deploy-settings` stamp claiming settings that were never applied; delete `~/.zeroclaw/.deploy-settings` once to force a clean re-apply.
- Pair a browser: `zeroclaw gateway get-paircode` in the container. Never set `require_pairing = false`.
- Logs: `journalctl --user -u zeroclaw`.
- A container previously deployed as Hermes on the same `DASHBOARD_PORT` still has `hermes-dashboard` holding the port; run `lxc delete --force <container>` before the first ZeroClaw deploy.

## Pi

- `pi/`: no dashboard; SSH in and run `pi`. `pi/deploy.py` owns `~/.pi/agent/models.json` and `settings.json` and rewrites them every run, so changes made inside Pi (`/model`, `/thinking` save, changelog state) are reset.
- Node comes from the `node` snap (`NODE_SNAP_CHANNEL`, default `26/stable`). The tool test runs `pi -p --no-session` asking for `uname -a`.

## Container can't reach the internet

If the LXC cannot connect to the internet, stage 2 fails like this:

    [10.98.171.146] curl: (28) Failed to connect to hermes-agent.nousresearch.com port 443 after 133407 ms: Could not connect to server
    [10.98.171.146] Error: executed 0 commands

Run these on the host to allow traffic from `lxdbr0` and its replies through Docker's `DOCKER-USER` chain:

```bash
sudo iptables -I DOCKER-USER -i lxdbr0 -j ACCEPT
sudo iptables -I DOCKER-USER -o lxdbr0 -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT
```

The rules don't survive a host reboot. Re-run them, or persist with:

```bash
sudo mkdir -p /etc/iptables
sudo iptables-save | sudo tee /etc/iptables/rules.v4
```

Then restore them at boot with `/etc/systemd/system/iptables-restore.service`:

```ini
[Unit]
Description=Restore iptables rules
Before=network-pre.target

[Service]
Type=oneshot
ExecStart=/sbin/iptables-restore /etc/iptables/rules.v4

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now iptables-restore.service
```
