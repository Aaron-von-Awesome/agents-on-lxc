"""Stage 1: create/start the LXD container and open SSH (+ dashboard, when the variant has one) access. Run on the LXD host."""

import os
import shlex
import subprocess

from pyinfra import host
from pyinfra.api import QuoteString, StringCommand
from pyinfra.facts.lxd import LxdContainers
from pyinfra.operations import python, server

import settings
from helpers import (
    NESTING_CONFIG,
    authorize_key_script,
    container_ipv4,
    container_state,
    ensure_keypair,
    lxc_list,
    nesting_missing,
    port_conflict,
    proxy_device_commands,
    proxy_device_matches,
    read_pubkey,
)
from settings import (
    CONTAINER,
    IMAGE,
    PUBKEY_PATH,
    SSH_KEY_PATH,
    SSH_USER,
)

DASHBOARD_PORT = getattr(settings, "DASHBOARD_PORT", None)
PROXY_DEVICE = getattr(settings, "PROXY_DEVICE", None)
KNOWN_HOSTS = os.path.expanduser("~/.ssh/known_hosts")
ensure_keypair(SSH_KEY_PATH)
pubkey = read_pubkey(PUBKEY_PATH)
containers = host.get_fact(LxdContainers)
state = container_state(containers, CONTAINER)
LISTEN = f"tcp:127.0.0.1:{DASHBOARD_PORT}"
CONNECT = f"tcp:127.0.0.1:{DASHBOARD_PORT}"
if DASHBOARD_PORT is not None:
    conflict = port_conflict(containers, CONTAINER, DASHBOARD_PORT)
    if conflict is not None:
        raise RuntimeError(conflict)


def forget_host_key() -> None:
    # A fresh container gets a new host key; drop any stale entry for the reused IP.
    ip = container_ipv4(lxc_list(), CONTAINER)
    if ip is None:
        raise RuntimeError(f"{CONTAINER} has no global IPv4 address")
    if os.path.exists(KNOWN_HOSTS):
        subprocess.run(["ssh-keygen", "-R", ip], check=True)


launch = None
if state == "absent":
    launch = server.shell(
        name="Launch container",
        commands=[
            StringCommand(
                "lxc launch",
                QuoteString(IMAGE),
                QuoteString(CONTAINER),
                "< /dev/null",
            )
        ],
    )
elif state == "stopped":
    server.shell(
        name="Start container",
        commands=[StringCommand("lxc start", QuoteString(CONTAINER))],
    )

APT = (
    "DEBIAN_FRONTEND=noninteractive apt-get -q -y -o DPkg::Lock::Timeout=300"
    " -o Dpkg::Options::=--force-confdef -o Dpkg::Options::=--force-confold"
)


def wait_for_cloud_init(name: str) -> None:
    server.shell(
        name=name,
        commands=[
            StringCommand(
                "lxc exec", QuoteString(CONTAINER), "-- cloud-init status --wait"
            )
        ],
        _success_exit_codes=[0, 2],  # 2 = done with recoverable errors
    )


def in_container(script: str) -> StringCommand:
    return StringCommand(
        "lxc exec", QuoteString(CONTAINER), "-- sh -c", QuoteString(script)
    )


wait_for_cloud_init("Wait for cloud-init")

# Restart only when the upgrade installs something, so a re-run does not bounce the dashboard.
server.shell(
    name="Upgrade packages, restart if any changed",
    commands=[
        StringCommand(
            in_container(f"{APT} update"),
            "&& if",
            in_container(f"{APT} -s full-upgrade | grep -q '^Inst'"),
            "; then",
            in_container(f"{APT} full-upgrade"),
            "&& lxc restart",
            QuoteString(CONTAINER),
            "; fi",
        )
    ],
    _timeout=1800,
)

# Group first, so the Docker snap picks it up on its first start (canonical/docker-snap README),
# and before the nesting restart, so the user's services start with the group.
# Members of the docker group are effectively root in the container.
user = shlex.quote(SSH_USER)
server.shell(
    name="Add SSH user to docker group",
    commands=[
        StringCommand(
            in_container(
                "{ getent group docker >/dev/null || addgroup --system docker; }"
                f" && {{ id -nG {user} | tr ' ' '\\n' | grep -qx docker || adduser {user} docker; }}"
            )
        )
    ],
)

# Docker runs inside the container, which needs nesting. Restarts only when a key is missing.
if nesting_missing(containers, CONTAINER):
    server.shell(
        name="Enable nesting, restart",
        commands=[
            StringCommand(
                "lxc config set",
                QuoteString(CONTAINER),
                *[QuoteString(f"{k}={v}") for k, v in NESTING_CONFIG.items()],
            ),
            StringCommand("lxc restart", QuoteString(CONTAINER)),
        ],
    )

wait_for_cloud_init("Wait for boot after restart")


def snap_missing(name: str):
    def check() -> bool:
        return (
            subprocess.run(
                ["lxc", "exec", CONTAINER, "--", "snap", "list", name],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            ).returncode
            != 0
        )

    return check


server.shell(
    name="Install Helix snap",
    commands=[StringCommand(in_container("snap install helix --classic"))],
    _if=snap_missing("helix"),
)

server.shell(
    name="Install Docker snap",
    commands=[StringCommand(in_container("snap install docker"))],
    _if=snap_missing("docker"),
)

if launch is not None:
    python.call(
        name="Forget stale SSH host key",
        function=forget_host_key,
        _if=launch.did_change,
    )

server.shell(
    name="Authorize operator SSH key",
    commands=[
        StringCommand(
            "lxc exec",
            QuoteString(CONTAINER),
            "-- su -",
            QuoteString(SSH_USER),
            "-c",
            QuoteString(authorize_key_script(pubkey)),
        )
    ],
)

if DASHBOARD_PORT is not None and not proxy_device_matches(
    containers, CONTAINER, PROXY_DEVICE, LISTEN, CONNECT
):
    server.shell(
        name="Set dashboard proxy device",
        commands=proxy_device_commands(
            containers, CONTAINER, PROXY_DEVICE, LISTEN, CONNECT
        ),
    )
