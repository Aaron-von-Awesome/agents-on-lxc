"""Stage 2: install and configure ZeroClaw in the container. Run on the LXD host."""

import io
from hashlib import sha256

from pyinfra import host
from pyinfra.api import QuoteString, StringCommand
from pyinfra.facts.files import File, Sha256File
from pyinfra.operations import files, server, systemd

import settings
from helpers import (
    chat_test_wanted,
    enable_linger,
    read_api_key,
    wait_for_url,
)

# Checked before the settings imports below: a hermes variant has no ZEROCLAW_INSTALL_URL.
if settings.AGENT != "zeroclaw":
    raise RuntimeError("zeroclaw/deploy.py needs AGENT_VARIANT=zeroclaw/<name>")
if host.state.config.DIFF:
    raise RuntimeError(
        "--diff would print the API key file contents; re-run without --diff"
    )

from settings import (
    BASE_URL,
    CONTEXT_LENGTH,
    DASHBOARD_PORT,
    MODEL,
    SANDBOX_BACKEND,
    SSH_USER,
    ZEROCLAW_INSTALL_URL,
)
from zeroclaw.helpers import (
    apply_settings_commands,
    config_toml,
    stamp_text,
    workspace_path,
)

HOME = f"/home/{SSH_USER}"
ZC = f"{HOME}/.cargo/bin/zeroclaw"
ZC_DIR = f"{HOME}/.zeroclaw"
UNIT = "zeroclaw.service"
CONFIG = f"{ZC_DIR}/config.toml"
KEYFILE = f"{ZC_DIR}/.api-key"
STAMP = f"{ZC_DIR}/.deploy-settings"

api_key = read_api_key(BASE_URL, MODEL, CONTEXT_LENGTH)

stamp = stamp_text(settings, api_key)
# The stamp records what was applied and is written only after a
# successful restart (below), so this compare sees any change that an
# earlier interrupted run left unapplied.
needs_apply = host.get_fact(Sha256File, path=STAMP) != sha256(stamp.encode()).hexdigest()

install = None
if host.get_fact(File, path=ZC) is None:
    install = server.shell(
        name="Run the ZeroClaw installer",
        commands=[
            StringCommand(
                "curl -fsSL",
                QuoteString(ZEROCLAW_INSTALL_URL),
                "| sh -s -- --prebuilt --skip-quickstart --no-modify-path && test -x",
                QuoteString(ZC),
            )
        ],
    )

files.directory(name="Create ~/.zeroclaw", path=ZC_DIR, mode="700")
files.directory(
    name="Create agent workspace", path=workspace_path(settings), mode="700"
)

cfg = None
if host.get_fact(File, path=CONFIG) is None:
    cfg = files.put(
        name="Write first-run config",
        src=io.StringIO(config_toml(settings, api_key)),
        dest=CONFIG,
        mode="600",
    )

# Removed again by the apply step once the key is in config.toml.
files.put(
    name="Stage API key",
    src=io.StringIO(api_key),
    dest=KEYFILE,
    mode="600",
    _if=lambda: needs_apply,
)
server.shell(
    name="Apply ZeroClaw settings",
    commands=apply_settings_commands(ZC, settings, CONFIG, KEYFILE),
    _if=lambda: needs_apply,
)

if host.get_fact(File, path=f"{HOME}/.config/systemd/user/{UNIT}") is None:
    server.shell(
        name="Install ZeroClaw service",
        commands=[StringCommand(ZC, "service install")],
    )

# The installer ran with --no-modify-path; put zeroclaw on PATH for SSH logins.
files.line(
    name="Add ~/.cargo/bin to PATH in ~/.profile",
    path=f"{HOME}/.profile",
    line='export PATH="$HOME/.cargo/bin:$PATH"',
    escape_regex_characters=True,
)

# Linger starts the user manager at boot, so the gateway runs without a login.
enable_linger(SSH_USER)

systemd.service(
    name="Enable and start ZeroClaw",
    service=UNIT,
    running=True,
    enabled=True,
    user_mode=True,
)

server.shell(
    name="Restart ZeroClaw after settings change",
    commands=[StringCommand("systemctl --user restart", QuoteString(UNIT))],
    _if=lambda: needs_apply or (cfg is not None and cfg.did_change()),
)

# The key's hash is in the stamp, so a new LLAMA_API_KEY re-applies and restarts like a setting.
# The stamp is written last so it can never claim settings that were not applied and restarted.
files.put(
    name="Record deploy settings",
    src=io.StringIO(stamp),
    dest=STAMP,
    mode="600",
    _if=lambda: needs_apply,
)

server.shell(
    name="Wait for ZeroClaw gateway",
    commands=[wait_for_url(DASHBOARD_PORT, "/health")],
)

server.shell(
    name="Check zeroclaw status",
    commands=[StringCommand(ZC, "status --format exit-code")],
)


# In the Docker sandbox, uname -a shows a random container ID, not this hostname.
# The sandbox fails open, so a reply with this hostname means it did not engage.
# `zeroclaw agent` refuses while the service owns ~/.zeroclaw/data, so stop it for the
# test and always start it again. timeout 540 ends the agent before pyinfra's 600 s.
sandbox_check = (
    ""
    if SANDBOX_BACKEND == "none"
    else ' && ! printf %s "$out" | grep -qF "$(hostname)"'
)
server.shell(
    name="Agent tool-call test",
    commands=[
        StringCommand(
            "systemctl --user stop",
            QuoteString(UNIT),
            "; ( out=$( timeout 540",
            ZC,
            "agent -a main -m",
            QuoteString("Run uname -a in the shell and reply with its exact output."),
            "< /dev/null) && printf '%s\\n' \"$out\" >&2",
            '&& printf %s "$out" | grep -qF "$(uname -r)"' + sandbox_check,
            "); rc=$?; systemctl --user start",
            QuoteString(UNIT),
            "&& exit $rc",
        )
    ],
    _if=lambda: chat_test_wanted(install, host.data),
    _timeout=600,
)
