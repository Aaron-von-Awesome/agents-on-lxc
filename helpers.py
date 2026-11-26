import json
import os
import shlex
import socket
import subprocess
import urllib.request
from getpass import getpass
from pathlib import Path
from typing import Literal

from pyinfra import host
from pyinfra.api import QuoteString, StringCommand
from pyinfra.facts.files import File
from pyinfra.operations import server


def lxc_list() -> list[dict]:
    out = subprocess.run(
        ["lxc", "list", "--format", "json"],
        check=True,
        stdout=subprocess.PIPE,
        text=True,
    )
    return json.loads(out.stdout)


def ensure_keypair(key: Path) -> None:
    if key.exists():
        return
    key.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    # No passphrase: pyinfra cannot prompt for one.
    subprocess.run(
        ["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(key)], check=True
    )


def read_pubkey(path: Path) -> str:
    try:
        return path.read_text().strip()
    except FileNotFoundError as e:
        raise FileNotFoundError(f"SSH public key not found: {path}") from e


def check_api_key(api_key: str) -> str:
    if not api_key.strip():
        raise ValueError("API key is empty.")
    if any(c in api_key for c in "'\"\\\n\r"):
        raise ValueError(
            "API key contains a quote, backslash, or newline; it cannot be stored safely."
        )
    return api_key


def flag_is_true(value: object) -> bool:
    # pyinfra --data values are strings; "false" must not count as set.
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def wait_for_url(port: int, path: str) -> StringCommand:
    # 100 tries x 3s: the dashboard can take a while to answer after a restart.
    return StringCommand(
        "for i in $(seq 100); do",
        "curl -sf",
        QuoteString(f"http://127.0.0.1:{port}{path}"),
        "> /dev/null && exit 0;",
        "sleep 3; done; exit 1",
    )


def enable_linger(ssh_user: str) -> None:
    # Linger starts the user manager at boot, so user services run without a login.
    if host.get_fact(File, path=f"/var/lib/systemd/linger/{ssh_user}") is None:
        server.shell(
            name="Enable linger",
            commands=[StringCommand("loginctl enable-linger", QuoteString(ssh_user))],
            _sudo=True,
        )


def chat_test_wanted(install, host_data) -> bool:
    # First install, or --data chat_test=true.
    return (install is not None and install.did_change()) or flag_is_true(
        host_data.get("chat_test")
    )


def authorize_key_script(pubkey: str) -> str:
    return f"""set -eu
key={shlex.quote(pubkey)}
mkdir -p "$HOME/.ssh"
chmod 700 "$HOME/.ssh"
touch "$HOME/.ssh/authorized_keys"
chmod 600 "$HOME/.ssh/authorized_keys"
grep -qxF "$key" "$HOME/.ssh/authorized_keys" || printf '%s\\n' "$key" >> "$HOME/.ssh/authorized_keys"
"""


def _find(containers: list[dict], name: str) -> dict | None:
    return next((c for c in containers if c.get("name") == name), None)


def container_state(
    containers: list[dict], name: str
) -> Literal["absent", "stopped", "running"]:
    c = _find(containers, name)
    if c is None:
        return "absent"
    return "running" if c.get("status") == "Running" else "stopped"


def container_ipv4(containers: list[dict], name: str) -> str | None:
    c = _find(containers, name) or {}
    addrs = (((c.get("state") or {}).get("network") or {}).get("eth0") or {}).get(
        "addresses"
    ) or []
    return next(
        (
            a["address"]
            for a in addrs
            if a.get("family") == "inet" and a.get("scope") == "global"
        ),
        None,
    )


def has_device(containers: list[dict], name: str, device: str) -> bool:
    return device in ((_find(containers, name) or {}).get("devices") or {})


# Docker inside an unprivileged container needs nesting plus these two syscall intercepts.
NESTING_CONFIG = {
    "security.nesting": "true",
    "security.syscalls.intercept.mknod": "true",
    "security.syscalls.intercept.setxattr": "true",
}


def nesting_missing(containers: list[dict], name: str) -> bool:
    # expanded_config includes values set through profiles.
    config = (_find(containers, name) or {}).get("expanded_config") or {}
    return any(config.get(k) != v for k, v in NESTING_CONFIG.items())


def proxy_device_matches(
    containers: list[dict], name: str, device: str, listen: str, connect: str
) -> bool:
    d = ((_find(containers, name) or {}).get("devices") or {}).get(device) or {}
    return (
        d.get("type") == "proxy"
        and d.get("listen") == listen
        and d.get("connect") == connect
    )


def proxy_device_commands(
    containers: list[dict], name: str, device: str, listen: str, connect: str
) -> list[StringCommand]:
    # Whole commands only: pyinfra runs each list item as its own shell command.
    commands: list[StringCommand] = []
    if has_device(containers, name, device):
        commands.append(
            StringCommand(
                "lxc config device remove",
                QuoteString(name),
                QuoteString(device),
            )
        )
    commands.append(
        StringCommand(
            "lxc config device add",
            QuoteString(name),
            QuoteString(device),
            "proxy",
            QuoteString(f"listen={listen}"),
            QuoteString(f"connect={connect}"),
        )
    )
    return commands


def port_free(port: int) -> bool:
    # Bind test on loopback, where the proxy listens. No SO_REUSEADDR: a live
    # listener on 127.0.0.1 or 0.0.0.0 must block this.
    with socket.socket() as s:
        try:
            s.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


def port_owner(containers: list[dict], port: int, exclude: str) -> str | None:
    # Any listen address counts, and profile devices show only in expanded_devices.
    return next(
        (
            c["name"]
            for c in containers
            if c["name"] != exclude
            for d in {
                **(c.get("expanded_devices") or {}),
                **(c.get("devices") or {}),
            }.values()
            if d.get("type") == "proxy"
            and d.get("listen", "").rsplit(":", 1)[-1] == str(port)
        ),
        None,
    )


def port_conflict(containers: list[dict], name: str, port: int) -> str | None:
    owner = port_owner(containers, port, name)
    if owner is not None:
        return f"Port {port} is already used by container {owner}; pick another DASHBOARD_PORT"
    # Our own proxy device holds the host port while the container runs; not a conflict.
    if port_owner(containers, port, "") is not None:
        return None
    if not port_free(port):
        return f"Port {port} is already used on this host; pick another DASHBOARD_PORT"
    return None


def _http_json(url: str, api_key: str) -> dict:
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {api_key}"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.load(r)


def preflight(base_url: str, model: str, context_length: int, api_key: str) -> None:
    base_url = base_url.rstrip("/")
    try:
        models = [
            m.get("id")
            for m in _http_json(f"{base_url}/models", api_key).get("data", [])
        ]
    except Exception as e:
        raise RuntimeError(f"GET /models failed: {e}") from e
    if model not in models:
        raise RuntimeError(f"model {model!r} not served; server lists {models}")
    root = base_url.removesuffix("/v1")
    try:
        n_ctx = (
            _http_json(f"{root}/props", api_key)
            .get("default_generation_settings", {})
            .get("n_ctx")
        )
    except Exception as e:
        raise RuntimeError(f"GET /props failed: {e}") from e
    if n_ctx != context_length:
        raise RuntimeError(
            f"per-slot context is {n_ctx}, expected {context_length} (check llama-server -c / -np)"
        )


def read_api_key(base_url: str, model: str, context_length: int) -> str:
    # LLAMA_API_KEY or a prompt; checked, then tried against the server before any write.
    api_key = check_api_key(
        (os.environ.get("LLAMA_API_KEY") or getpass("llama.cpp API key: ")).strip()
    )
    preflight(base_url, model, context_length, api_key)
    return api_key
