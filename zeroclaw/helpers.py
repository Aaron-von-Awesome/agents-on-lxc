import json
from hashlib import sha256

from pyinfra.api import QuoteString, StringCommand

PROVIDER = "llamacpp.local"
_PROVIDER_TABLE = f"providers.models.{PROVIDER}"


# Outside hidden ~/.zeroclaw: the Docker snap cannot mount hidden folders in $HOME for the sandbox.
def workspace_path(s) -> str:
    return f"/home/{s.SSH_USER}/zeroclaw-workspace"


def _settings(s) -> list[tuple[str, object]]:
    return [
        (f"{_PROVIDER_TABLE}.uri", s.BASE_URL),
        (f"{_PROVIDER_TABLE}.model", s.MODEL),
        (f"{_PROVIDER_TABLE}.context_window", s.CONTEXT_LENGTH),
        ("agents.main.model_provider", PROVIDER),
        ("agents.main.risk_profile", "main"),
        ("agents.main.runtime_profile", "main"),
        ("agents.main.workspace.path", workspace_path(s)),
        ("risk_profiles.main.level", s.RISK_LEVEL),
        ("risk_profiles.main.auto_approve", s.AUTO_APPROVE),
        ("risk_profiles.main.allowed_commands", s.ALLOWED_COMMANDS),
        ("risk_profiles.main.allowed_tools", s.ALLOWED_TOOLS),
        ("risk_profiles.main.workspace_only", s.WORKSPACE_ONLY),
        ("risk_profiles.main.sandbox_enabled", s.SANDBOX_BACKEND != "none"),
        ("risk_profiles.main.sandbox_backend", s.SANDBOX_BACKEND),
        ("runtime_profiles.main.memory_recall_limit", s.MEMORY_RECALL_LIMIT),
        ("web_search.enabled", s.WEB_SEARCH_ENABLED),
        # never beyond loopback: pairing is the only gate behind the LXD proxy
        ("gateway.host", "127.0.0.1"),
        ("gateway.port", s.DASHBOARD_PORT),
        ("gateway.check_updates", s.CHECK_UPDATES),
        ("tools.optional", s.TOOLS_OPTIONAL),
        ("skills.skill_creation.enabled", s.SKILL_CREATION),
        ("skills.skill_improvement.enabled", s.SKILL_IMPROVEMENT),
        ("web_fetch.enabled", bool(s.WEB_FETCH_DOMAINS)),
        # ignored while disabled
        ("web_fetch.allowed_domains", s.WEB_FETCH_DOMAINS or ["*"]),
        ("http_request.enabled", s.HTTP_REQUEST_ENABLED),
        ("browser.enabled", s.BROWSER_ENABLED),
        ("mcp.enabled", s.MCP_ENABLED),
        ("scheduler.enabled", s.SCHEDULER_ENABLED),
        ("memory.backend", s.MEMORY_BACKEND),
        ("memory.auto_save", s.MEMORY_AUTO_SAVE),
        ("memory.hygiene_enabled", s.MEMORY_HYGIENE),
        ("memory.archive_after_days", s.MEMORY_ARCHIVE_AFTER_DAYS),
        ("memory.purge_after_days", s.MEMORY_PURGE_AFTER_DAYS),
        ("memory.search_mode", s.MEMORY_SEARCH_MODE),
        ("memory.embedding_provider", s.MEMORY_EMBEDDING_PROVIDER),
        ("memory.snapshot_enabled", s.MEMORY_SNAPSHOT),
        ("memory.snapshot_on_hygiene", s.MEMORY_SNAPSHOT_ON_HYGIENE),
        ("memory.consolidation_extract_facts", s.MEMORY_EXTRACT_FACTS),
        ("memory.response_cache_enabled", s.MEMORY_RESPONSE_CACHE),
        ("knowledge.enabled", s.KNOWLEDGE_ENABLED),
        ("sop.procedural_memory_enabled", s.SOP_PROCEDURAL_MEMORY),
        ("sop.sops_dir", s.SOP_SOPS_DIR),
    ]


def config_set_settings(s) -> list[tuple[str, str]]:
    return [(p, v if isinstance(v, str) else json.dumps(v)) for p, v in _settings(s)]


def stamp_text(s, api_key: str) -> str:
    return (
        "".join(f"{p}={v}\n" for p, v in config_set_settings(s))
        + f"api_key_sha256={sha256(api_key.encode()).hexdigest()}\n"
    )


# Sets api_key in the provider table from a file, so the key never reaches a command line.
# `config set` reads secrets only from a terminal; ZeroClaw accepts a plaintext api_key.
_SET_API_KEY = """\
import json, os, sys
cfg, keyfile, table = sys.argv[1:]
key = open(keyfile).read().strip()
lines = open(cfg).read().splitlines(keepends=True)
start = next((n for n, l in enumerate(lines) if l.strip() == f"[{table}]"), None)
if start is None:
    sys.exit(f"[{table}] not found in {cfg}; delete it so the deploy writes a first-run config")
end = next((n for n in range(start + 1, len(lines)) if lines[n].lstrip().startswith("[")), len(lines))
new = f"api_key = {json.dumps(key)}\\n"
hit = [n for n in range(start + 1, end) if lines[n].split("=")[0].strip() == "api_key"]
if hit:
    lines[hit[0]] = new
else:
    lines.insert(start + 1, new)
fd = os.open(cfg + ".tmp", os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
with os.fdopen(fd, "w") as f:
    f.write("".join(lines))
os.replace(cfg + ".tmp", cfg)
"""


def set_api_key_command(config: str, keyfile: str) -> StringCommand:
    return StringCommand(
        "python3 -c",
        QuoteString(_SET_API_KEY),
        QuoteString(config),
        QuoteString(keyfile),
        QuoteString(_PROVIDER_TABLE),
        "&& rm -f",
        QuoteString(keyfile),
    )


def apply_settings_commands(
    zc: str, s, config: str, keyfile: str
) -> list[StringCommand]:
    return [
        set_api_key_command(config, keyfile),
        *(
            StringCommand(
                zc, "config set --no-interactive", QuoteString(p), QuoteString(v)
            )
            for p, v in config_set_settings(s)
        ),
    ]


def config_toml(s, api_key: str) -> str:
    tables: dict[str, list[tuple[str, object]]] = {}
    for path, v in _settings(s):
        table, _, key = path.rpartition(".")
        tables.setdefault(table, []).append((key, v))
    tables[_PROVIDER_TABLE].append(("api_key", api_key))
    out = ["schema_version = 4"]
    for table, kvs in tables.items():
        out += ["", f"[{table}]", *(f"{k} = {json.dumps(v)}" for k, v in kvs)]
    return "\n".join(out) + "\n"
