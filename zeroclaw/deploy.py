"""Stage 2: install and configure ZeroClaw in the container. Run on the LXD host."""

import io
import os
from getpass import getpass

import settings
from pyinfra import host
from pyinfra.api import QuoteString, StringCommand
from pyinfra.facts.files import File
from pyinfra.operations import files, server, systemd

# Checked before the settings imports below: a hermes variant has no ZEROCLAW_INSTALL_URL.
if settings.AGENT != "zeroclaw":
    raise RuntimeError("zeroclaw/deploy.py needs AGENT_VARIANT=zeroclaw/<name>")
if host.state.config.DIFF:
    raise RuntimeError(
        "--diff would print the API key file contents; re-run without --diff"
    )

from helpers import check_api_key, chat_test_wanted, preflight, wait_for_url  # noqa: E402
from settings import (  # noqa: E402
    BASE_URL,
    CONTEXT_LENGTH,
    DASHBOARD_PORT,
    MODEL,
    SSH_USER,
    ZEROCLAW_INSTALL_URL,
)
from zeroclaw.helpers import (  # noqa: E402
    apply_settings_commands,
    config_set_settings,
    config_toml,
    restart_commands,
)

HOME = f"/home/{SSH_USER}"
ZC = f"{HOME}/.cargo/bin/zeroclaw"
ZC_DIR = f"{HOME}/.zeroclaw"
UNIT = "zeroclaw.service"

api_key = check_api_key(
    (os.environ.get("LLAMA_API_KEY") or getpass("llama.cpp API key: ")).strip()
)
preflight(BASE_URL, MODEL, CONTEXT_LENGTH, api_key)

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

cfg = None
if host.get_fact(File, path=f"{ZC_DIR}/config.toml") is None:
    cfg = files.put(
        name="Write first-run config",
        src=io.StringIO(config_toml(settings, api_key)),
        dest=f"{ZC_DIR}/config.toml",
        mode="600",
    )

stamp = files.put(
    name="Record deploy settings",
    src=io.StringIO("".join(f"{p}={v}\n" for p, v in config_set_settings(settings))),
    dest=f"{ZC_DIR}/.deploy-settings",
    mode="600",
)

# The stamp is only "committed" (renamed back) after a successful restart, so any failure in
# between leaves it missing and the next run re-applies.
STAMP = f"{ZC_DIR}/.deploy-settings"
PENDING = f"{STAMP}.pending"
server.shell(
    name="Apply ZeroClaw settings",
    commands=apply_settings_commands(ZC, settings, STAMP, PENDING),
    _if=stamp.did_change,
)

if host.get_fact(File, path=f"{HOME}/.config/systemd/user/{UNIT}") is None:
    server.shell(
        name="Install ZeroClaw service",
        commands=[StringCommand(ZC, "service install")],
    )

# Linger starts the user manager at boot, so the gateway runs without a login.
if host.get_fact(File, path=f"/var/lib/systemd/linger/{SSH_USER}") is None:
    server.shell(
        name="Enable linger",
        commands=[StringCommand("loginctl enable-linger", QuoteString(SSH_USER))],
        _sudo=True,
    )

systemd.service(
    name="Enable and start ZeroClaw",
    service=UNIT,
    running=True,
    enabled=True,
    user_mode=True,
)

server.shell(
    name="Restart ZeroClaw after settings change",
    commands=restart_commands(UNIT, STAMP, PENDING),
    _if=lambda: stamp.did_change() or (cfg is not None and cfg.did_change()),
)

server.shell(
    name="Wait for ZeroClaw gateway",
    commands=[wait_for_url(DASHBOARD_PORT, "/health")],
)

server.shell(
    name="Check zeroclaw status",
    commands=[StringCommand(ZC, "status --format exit-code")],
)


server.shell(
    name="Agent tool-call test",
    commands=[
        StringCommand(
            ZC,
            "agent -a main -m",
            QuoteString("Run uname -a in the shell and reply with its exact output."),
            '< /dev/null | tee /dev/stderr | grep -qF "$(uname -r)"',
        )
    ],
    _if=lambda: chat_test_wanted(install, host.data),
    _timeout=600,
)
