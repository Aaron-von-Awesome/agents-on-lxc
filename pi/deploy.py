"""Stage 2: install and configure Pi in the container. Run on the LXD host."""

import io

from pyinfra import host
from pyinfra.api import QuoteString, StringCommand
from pyinfra.facts.files import File
from pyinfra.facts.server import Command
from pyinfra.operations import files, server

import settings
from helpers import chat_test_wanted, read_api_key

# Checked before the settings imports below: other variants have no PI_INSTALL_URL.
if settings.AGENT != "pi":
    raise RuntimeError("pi/deploy.py needs AGENT_VARIANT=pi/<name>")
if host.state.config.DIFF:
    raise RuntimeError(
        "--diff would print the API key file contents; re-run without --diff"
    )

from pi.helpers import models_json, settings_json
from settings import (
    BASE_URL,
    CONTEXT_LENGTH,
    MODEL,
    NODE_SNAP_CHANNEL,
    PI_INSTALL_URL,
    SSH_USER,
)

HOME = f"/home/{SSH_USER}"
PI_DIR = f"{HOME}/.pi/agent"
# The non-login SSH shell has neither directory on PATH.
PATH_PREFIX = f"PATH={HOME}/.local/bin:/snap/bin:$PATH"

api_key = read_api_key(BASE_URL, MODEL, CONTEXT_LENGTH)

# Runs when Node is missing or tracks another channel (column 4 of `snap list`).
server.shell(
    name="Install Node snap, or move it to NODE_SNAP_CHANNEL",
    commands=[
        (
            "if snap list node >/dev/null 2>&1;"
            f" then snap refresh node --channel={NODE_SNAP_CHANNEL};"
            f" else snap install node --channel={NODE_SNAP_CHANNEL} --classic; fi"
        )
    ],
    _sudo=True,
    _if=lambda: (
        host.get_fact(Command, "snap list node 2>/dev/null | awk 'NR==2 {print $4}'")
        != NODE_SNAP_CHANNEL
    ),
)

install = server.shell(
    name="Run the Pi installer",
    commands=[
        StringCommand(
            "mkdir -p ~/.local/bin && curl -fsSL",
            QuoteString(PI_INSTALL_URL),
            "| env",
            PATH_PREFIX,
            "sh",
        )
    ],
    _if=lambda: not host.get_fact(File, path=f"{PI_DIR}/install/managed-install.json"),
    _timeout=900,
)

files.directory(name="Create ~/.pi/agent", path=PI_DIR, mode="700")
files.put(
    name="Write Pi models.json",
    src=io.StringIO(models_json(settings, api_key)),
    dest=f"{PI_DIR}/models.json",
    mode="600",
)
files.put(
    name="Write Pi settings.json",
    src=io.StringIO(settings_json(settings)),
    dest=f"{PI_DIR}/settings.json",
    mode="600",
)

server.shell(
    name="Agent tool-call test",
    commands=[
        StringCommand(
            f"cd {HOME} && env {PATH_PREFIX} pi -p --no-session",
            QuoteString("Run uname -a in the shell and reply with its exact output."),
            '< /dev/null | tee /dev/stderr | grep -qF "$(uname -r)"',
        )
    ],
    _if=lambda: chat_test_wanted(install, host.data),
    _timeout=600,
)
