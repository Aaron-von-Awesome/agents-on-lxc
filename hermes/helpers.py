import json
import re
from urllib.parse import urlparse

from pyinfra.api import QuoteString, StringCommand

import helpers
import settings


def key_env_for(base_url: str) -> str:
    # Same rule as Hermes custom_endpoint_key_env (hermes_cli/config.py), keyed on host:port.
    slug = re.sub(
        r"[^A-Z0-9]+", "_", urlparse(base_url).netloc.rpartition("@")[2].upper()
    ).strip("_")
    return f"HERMES_CUSTOM_{slug}_API_KEY" if slug else "HERMES_CUSTOM_API_KEY"


def env_line(key_env: str, api_key: str) -> str:
    helpers.check_api_key(api_key)
    # Single quotes: python-dotenv would expand `$` and strip ` #...` in an unquoted value.
    return f"{key_env}='{api_key}'\n"


def merge_env_command(env: str, env_llama: str, key_env: str) -> StringCommand:
    # Reads the key from env_llama, so it never appears on a command line.
    return StringCommand(
        "touch",
        QuoteString(env),
        "&& { grep -qxFf",
        QuoteString(env_llama),
        QuoteString(env),
        "|| {",
        "sed -i",
        QuoteString(f"/^{key_env}=/d"),
        QuoteString(env),
        "&& sed -i -e",
        QuoteString("$a\\"),
        QuoteString(env),
        "&& cat",
        QuoteString(env_llama),
        ">>",
        QuoteString(env),
        "; } ; }",
        "&& chmod 600",
        QuoteString(env),
    )


def config_settings() -> list[tuple[str, str]]:
    s = settings
    key_env = key_env_for(s.BASE_URL)
    values = {
        # provider before base_url: a provider switch clears the old route's base_url
        "model.provider": "custom",
        "model.base_url": s.BASE_URL,
        "model.default": s.MODEL,
        "model.api_key": "${" + key_env + "}",
        "providers": {
            s.PROVIDER_KEY: {
                "name": s.PROVIDER_NAME,
                "base_url": s.BASE_URL,
                "key_env": key_env,
                "default_model": s.MODEL,
                "models": {s.MODEL: {"context_length": s.CONTEXT_LENGTH}},
            }
        },
        "terminal.backend": "local",
        "agent.max_turns": s.MAX_TURNS,
        "agent.reasoning_effort": s.REASONING_EFFORT,
        "agent.disabled_toolsets": s.DISABLED_TOOLSETS,
        **{f"platform_toolsets.{p}": t for p, t in s.ENABLED_PLATFORM_TOOLSETS.items()},
        "plugins.enabled": s.PLUGINS_ENABLED,
        "plugins.disabled": s.PLUGINS_DISABLED,
        "compression.enabled": True,
        "memory.memory_enabled": True,
        "memory.user_profile_enabled": True,
        "checkpoints.enabled": False,
        "smart_model_routing.enabled": False,
        # Replaces Hermes' built-in default preset (cloud models) with the variant's own model.
        "moa.default_preset": "default",
        "moa.presets.default": {
            "enabled": s.MOA_ENABLED,
            "reference_models": [{"provider": s.PROVIDER_KEY, "model": s.MODEL}],
            "aggregator": {"provider": s.PROVIDER_KEY, "model": s.MODEL},
        },
    }
    return [(k, v if isinstance(v, str) else json.dumps(v)) for k, v in values.items()]


def dashboard_unit(port: int) -> str:
    return f"""[Unit]
Description=Hermes Agent web dashboard
After=network-online.target

[Service]
ExecStart=%h/.local/bin/hermes dashboard --host 127.0.0.1 --port {port} --no-open
Restart=always
RestartSec=10
# Exit 78: Hermes refuses because another dashboard already serves this host.
RestartPreventExitStatus=78

[Install]
WantedBy=default.target
"""
