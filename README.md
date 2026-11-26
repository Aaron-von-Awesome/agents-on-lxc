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

Operating rules, gotchas, recovery and ZeroClaw procedures live in
[AGENTS.md](AGENTS.md) — read them before varying these commands.

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
