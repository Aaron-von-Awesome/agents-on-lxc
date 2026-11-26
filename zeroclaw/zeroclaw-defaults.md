# ZeroClaw defaults

A default ZeroClaw has nearly every tool on, a sandbox only if you install one, and almost no limit on outbound web access. Plugins, external channels and self-learning are all off.

How the defaults were read: the release binary, the minimal `config.toml` this deploy writes, and `zeroclaw daemon` running. Facts come from the `zeroclaw/` clone's docs, checked against its code. Paths are relative to `zeroclaw/`.

**Default** column: **on** = on with no config · **off** = shipped but off until configured · **deploy** = turned on by the deploy's config.

**Approval rules:** under `supervised`, low-risk tools run, medium-risk tools ask first, and high-risk ones are blocked. With no one there to approve, a medium-risk call is refused.

## Tools

`tools.optional = ["*"]` by default, so every tool compiled into the binary is offered to the agent. Setting `optional = []` cuts it to an 11-tool minimal set.

| Tool | Default | Risk | Touches |
|---|---|---|---|
| `shell` | on | medium/high | shell |
| `file_read`, `glob_search`, `content_search` | on | low | files |
| `file_write`, `file_edit` | on | medium | files |
| `git_operations` | on | medium (not confirmed) | files, network |
| `memory_store/recall/forget/export/purge` | on | recall is low | sqlite |
| `web_fetch` (any domain) | on | low | network |
| `http_request` (any domain, private hosts blocked) | on | GET low, POST medium/high | network |
| `web_search_tool` (DuckDuckGo) | on | low | network |
| `browser_open`, `weather` (wttr.in), `calculator`, `image_info`, `screenshot`, `backup`, `pushover` | on | mostly low | network, files |
| `cron_*`, `schedule` | on | – | scheduler |
| `spawn_subagent`, `send_message_to_peer`, `delegate` | on (delegation policy is `forbidden`) | – | agent loop |
| `model_switch`, `model_routing_config`, `proxy_config` | on, **the last two rewrite the config file** | – | config |
| `ask_user`, `escalate_to_human`, `TodoWrite`, `canvas`, `llm_task`, `tool_search`, and other chat helpers | on | – | channels, model |
| Browser automation, SaaS tools (Notion, Jira, MS365, Google), coding CLIs (claude_code, codex, …), image generation, a2a | off | – | external services |

## Skills, plugins, MCP

| Feature | Default |
|---|---|
| Skills in the workspace's `skills/` folder | on when the folder has any. **No bundled skills found** |
| `skill_creation` (the agent writes its own skills, after reflecting with the model) | **off** |
| `skill_improvement` (a background job patches existing skills) | **off** |
| `open_skills` (clones community skills from git), `allow_scripts` | off |
| Skill registry install | operator command (`zeroclaw skills install`), not the agent |
| WASM plugins | host built in: the prebuilt release includes `plugins-wasm-cranelift` (`Cargo.toml` `dist_extra_features`; only Android and 32-bit ARM archives drop it). But `plugins.enabled = false`, `auto_discover = false`, signature checks `disabled`. None bundled |
| MCP | `mcp.enabled = true`, but **no servers**. An agent connects only to the servers in its own `mcp_bundles` |

## Memory and learning

| Feature | Default |
|---|---|
| sqlite memory (`brain.db`), user messages saved automatically | on |
| Cleanup: archive after 7 days, purge after 30 | on |
| Keyword search; no embedding model | on |
| Up to 5 memories added to each turn, plus `MEMORY_SNAPSHOT.md` | on |
| Fact extraction, response cache, knowledge graph, learning procedures from SOPs (step-by-step workflows) | off |

## Channels, gateway, background work

| Feature | Default |
|---|---|
| CLI, a local socket (`daemon.sock`, mode 0600), ACP over the gateway's `/acp` WebSocket | on |
| Telegram, Discord, email, Matrix, WhatsApp-web, webhook channels | off, need config |
| Gateway on `127.0.0.1:42617`, `require_pairing = true`, public bind off | deploy |
| Gateway: `/admin/*` is loopback only; self-upgrade off | deploy |
| No pairing needed: `/health`, `/metrics`, `/pair`, `/pair/code`, `/api/docs`, `/api/openapi.json` | deploy |
| About 78 routes behind pairing: config CRUD, memory, cron, file browse (including mkdir/rmdir), `/ws/chat`, several webhooks | deploy |
| Cron scheduler (no jobs; missed jobs catch up on startup) | on |
| Hooks system (built-in hooks off) | on |
| Heartbeat (the agent starts turns on its own), SOP engine | off |

## Security defaults

- **Risk profile:** level `supervised`, `workspace_only = true`, medium-risk needs approval, high-risk commands blocked.
- **Default `allowed_commands`:** `git npm cargo ls cat grep find echo pwd wc head tail date df du uname uptime hostname python python3 pip node free`. `python`, `node`, `pip` and `npm` already let the agent run any code it writes. **This deploy narrows the list to `uname`.**
- **`forbidden_paths`:** `/etc /root /home /usr /bin /sbin /lib /opt /boot /dev /proc /sys /var /tmp ~/.ssh ~/.gnupg ~/.aws ~/.config`. The more specific workspace path still wins, so the workspace works even though it's under `/home`.
- **Default auto-approve list:** `file_read`, `memory_recall`, `web_search_tool`, `web_fetch`, `calculator`, `glob_search`, `content_search`, `image_info`, `weather`, `tool_search`, `browser_open`. **This applies only to a profile named `default`.** The deploy's `main` profile auto-approves the eight tools in `zeroclaw/defaults.py` (`AUTO_APPROVE`).
- **Sandbox:** set to `auto`, which uses firejail, then Docker, then **nothing**. Landlock isn't built into the release binary, so a stock container likely runs **unsandboxed**.
- **Limits:** 20 actions per hour, a 60-second shell timeout, and a $10/day cost limit that is **warn-only**.
- **On:** encrypted secrets, an audit log (not signed), and leak detection.
- **Off:** one-time passwords (OTP), emergency stop, observability.

## Outbound network

- **Update check:** on. It polls GitHub while the dashboard is open.
- **Agent tools:** DuckDuckGo search, `web_fetch` and `http_request` to any domain, and weather from wttr.in.
- **LLM calls:** only the llama.cpp provider. No telemetry found, though not every crate was audited for it.
- **Hardware and peripherals:** not in the release binary.

## What "function and learn" depends on

- **Tools:** `shell`, the `file_*`, `glob_search` and `content_search` tools, `memory_*` (sqlite), `web_fetch` and `web_search_tool`.
- **Skills:** workspace skills, plus `skill_creation` and `skill_improvement`. **Both of those are off by default, so a default install doesn't learn new skills.**
- **Background and access:** the cron scheduler, and the gateway with pairing.

## Known doc drift in `zeroclaw/`

- `security/autonomy.md` uses old tool names (`file_list`, `memory_search`, `http`, `time`).
- The comment on `workspace_only` says it defaults to off; the code makes it on.
- `getting-started/quickstart.md` (Plugins) says release archives are built without `plugins-wasm`, so Quickstart has no Plugins row. Stale: `Cargo.toml` `dist_extra_features` adds `plugins-wasm-cranelift` to the standard release (`xtask/src/generate/spec.rs::dist_extra_features` reads it).

## Not checked

- The channel, cron, heartbeat and SOP pages were not read in depth.
- Which tools sit behind the remaining "–" risk entries is unconfirmed.

# Proposed hardened minimum

**Goal:** the agent can run tools, remember, and write or improve its own skills, and nothing else. The deploy already sets loopback-only gateway with pairing, a `main` risk profile at `supervised`, `allowed_commands = ["uname"]` and `web_search.enabled = false`. Those stay.

Config paths come from `crates/zeroclaw-config/src/schema.rs` (`#[prefix]` attributes) and `builtin_tools.rs`. All rows are in `zeroclaw/defaults.py`; see Implemented below.

## Settings

| `defaults.py` name | Value | Config path | Effect |
|---|---|---|---|
| `TOOLS_OPTIONAL` | `["knowledge", "sop_list", "sop_execute", "sop_advance", "sop_approve", "sop_status", "sop_workshop"]` | `tools.optional` | The 11 core tools plus `knowledge` and the six SOP tools. Drops `model_routing_config`, `proxy_config`, cron, browser, SaaS, delegation and the chat helpers. Also shrinks the prompt for the local model |
| `ALLOWED_TOOLS` | `["content_search", "file_edit", "file_read", "file_write", "git_operations", "glob_search", "knowledge", "memory_forget", "memory_recall", "memory_store", "shell", "sop_advance", "sop_approve", "sop_execute", "sop_list", "sop_status", "sop_workshop", "web_fetch"]` (sorted) | `risk_profiles.main.allowed_tools` | Closed set for built-ins and MCP. All of the core 11, including `git_operations`, plus the `TOOLS_OPTIONAL` tools. Skill-defined tools stay available |
| `AUTO_APPROVE` | `["shell", "file_read", "file_write", "file_edit", "glob_search", "content_search", "memory_recall", "memory_store"]` | `risk_profiles.main.auto_approve` | Reads, writes and memory writes run unattended. `memory_forget` and `web_fetch` still ask |
| `ALLOWED_COMMANDS` | `["uname"]` (unchanged) | `risk_profiles.main.allowed_commands` | Never add `python`, `node`, `pip`, `npm`, `git` or `cargo`: each one runs any code |
| `WORKSPACE_ONLY` | `True` | `risk_profiles.main.workspace_only` | Set it explicitly; the schema comment and the code disagree on the default |
| `SKILL_CREATION` | `True` | `skills.skill_creation.enabled` | The agent writes a skill after a successful multi-step task. This is the "learn" switch |
| `SKILL_IMPROVEMENT` | `True` | `skills.skill_improvement.enabled` | A post-turn background job patches skills. It builds its own toolset (`skills_list`, `skill_view`, `skill_manage`), so the narrowed `tools.optional` does not block it |
| `WEB_FETCH_DOMAINS` | `[]` | `web_fetch.enabled` = `bool(list)`, `web_fetch.allowed_domains` = list | Off unless a variant names domains; `zeroius-clawius` does (see Implemented) |
| `HTTP_REQUEST_ENABLED` | `False` | `http_request.enabled` | No arbitrary API calls or POSTs |
| `BROWSER_ENABLED` | `False` | `browser.enabled` | Gates `browser_open`. Belt and braces: the tool is already outside the minimal set |
| `MCP_ENABLED` | `False` | `mcp.enabled` | No servers are configured anyway |
| `SCHEDULER_ENABLED` | `False` | `scheduler.enabled` | No cron jobs, no catch-up runs at startup. Skill improvement does not use it |
| `CHECK_UPDATES` | `False` | `gateway.check_updates` | Stops the GitHub poll |
| `SANDBOX_BACKEND` | `"docker"` | `risk_profiles.main.sandbox_enabled` = `backend != "none"`, `risk_profiles.main.sandbox_backend` | Explicit instead of `auto`. Each shell command runs in `docker run --rm --network none --memory 512m --cpus 1.0 alpine:latest`, with the workspace mounted read-only (`crates/zeroclaw-runtime/src/security/docker.rs`). `launch.py` installs the Docker snap, adds `SSH_USER` to the `docker` group and turns on LXD nesting. Set `"none"` to turn it off |
| `MEMORY_BACKEND` | `"sqlite"` | `memory.backend` | `brain.db` in the workspace. Same as the default, set explicitly |
| `MEMORY_AUTO_SAVE` | `True` | `memory.auto_save` | User messages are stored automatically. Learning needs it |
| `MEMORY_HYGIENE` | `True` | `memory.hygiene_enabled` | Runs the archive and purge below |
| `MEMORY_ARCHIVE_AFTER_DAYS` | `7` | `memory.archive_after_days` | Same as the default |
| `MEMORY_PURGE_AFTER_DAYS` | `30` | `memory.purge_after_days` | Same as the default |
| `MEMORY_SEARCH_MODE` | `"hybrid"` | `memory.search_mode` | Keyword-only while there is no embedder; picks up an embedder later without a second change |
| `MEMORY_EMBEDDING_PROVIDER` | `"none"` | `memory.embedding_provider` | No embedding model, no extra network calls |
| `MEMORY_SNAPSHOT` | `True` | `memory.snapshot_enabled` | **Turned on** (default off). Exports core memories to `MEMORY_SNAPSHOT.md` |
| `MEMORY_SNAPSHOT_ON_HYGIENE` | `True` | `memory.snapshot_on_hygiene` | **Turned on** (default off). Exports core memories during each hygiene pass |
| `MEMORY_EXTRACT_FACTS` | `True` | `memory.consolidation_extract_facts` | **Turned on** (default off). The model pulls facts out of conversations into core memories. Needs the sqlite backend |
| `MEMORY_RESPONSE_CACHE` | `True` | `memory.response_cache_enabled` | **Turned on** (default off). Repeated prompts are answered from the cache, not the model |
| `MEMORY_RECALL_LIMIT` | `5` | `runtime_profiles.main.memory_recall_limit` | Memories added to each turn. Same as the default; `agents.main.runtime_profile = "main"` links it |
| `KNOWLEDGE_ENABLED` | `True` | `knowledge.enabled` | **Turned on** (default off). The knowledge graph behind the `knowledge` tool |
| `SOP_PROCEDURAL_MEMORY` | `True` | `sop.procedural_memory_enabled` | **Turned on** (default off). The agent may propose and write back SOPs (step-by-step procedures). Marked experimental upstream |
| `SOP_SOPS_DIR` | `"shared/sops"` | `sop.sops_dir` | **Turned on** (default unset). Setting it is what enables SOP loading. Relative paths resolve against the install root, so this is `<install>/shared/sops` |

Left at the default, because the default is already the hardened value:
- `skills.allow_scripts = false`, `skills.open_skills_enabled = false`
- `plugins.enabled = false`
- delegation policy `forbidden`
- heartbeat off
- `block_high_risk_commands` and `require_approval_for_medium_risk` on

## Mapping onto the deploy

New lines for `_settings(s)` in `zeroclaw/helpers.py`:

```python
("tools.optional", s.TOOLS_OPTIONAL),
("risk_profiles.main.allowed_tools", s.ALLOWED_TOOLS),
("risk_profiles.main.workspace_only", s.WORKSPACE_ONLY),
("skills.skill_creation.enabled", s.SKILL_CREATION),
("skills.skill_improvement.enabled", s.SKILL_IMPROVEMENT),
("web_fetch.enabled", bool(s.WEB_FETCH_DOMAINS)),
("web_fetch.allowed_domains", s.WEB_FETCH_DOMAINS or ["*"]),  # ignored while disabled
("http_request.enabled", s.HTTP_REQUEST_ENABLED),
("browser.enabled", s.BROWSER_ENABLED),
("mcp.enabled", s.MCP_ENABLED),
("scheduler.enabled", s.SCHEDULER_ENABLED),
("gateway.check_updates", s.CHECK_UPDATES),
("risk_profiles.main.sandbox_enabled", s.SANDBOX_BACKEND != "none"),
("risk_profiles.main.sandbox_backend", s.SANDBOX_BACKEND),
```

## Risks and unverified points

- **Docker sandbox fails open.** If ZeroClaw cannot find or start `docker`, it logs a warning and runs shell commands unsandboxed (`crates/zeroclaw-runtime/src/security/detect.rs:455`). The deploy does not check for that warning.
- **`docker` on the service PATH.** The ZeroClaw unit sets no `PATH`, so it relies on the user manager's PATH including `/snap/bin` (snapd adds it through a systemd user-environment generator). Not checked.
- **Docker snap and hidden folders.** The snap reaches only files under `$HOME`, and the snap `home` interface does not cover hidden folders such as `~/.zeroclaw`. The deploy therefore sets `agents.main.workspace.path = /home/<SSH_USER>/zeroclaw-workspace` (`zeroclaw/helpers.py::workspace_path`, folder mode 700). `config.toml` and secrets stay in `~/.zeroclaw`, which the sandbox never mounts. `ZEROCLAW_CONFIG_DIR` / `ZEROCLAW_DATA_DIR` were not used: they are env-only, never saved to disk, and every `zeroclaw` call plus the systemd unit would need them (`docs/book/src/reference/env-vars.md`). The agent tool test (`uname -a`) fails if the mount is refused, and, when `SANDBOX_BACKEND` is not `none`, also fails if the reply shows the LXD container's hostname (the sandbox fell back to running unsandboxed). This checks the `zeroclaw agent` command, which runs the agent in its own process with the SSH login's groups, not the running service.
- **Shell commands cannot write.** The workspace is mounted read-only inside the sandbox and the network is off. File tools (`file_write`, `file_edit`) are not sandboxed and still write.
- **`docker` group.** `SSH_USER` is effectively root inside the LXD container. The LXD container is still the outer boundary.
- Firejail is not installed. It may fail in an unprivileged LXD container (it needs setuid and user namespaces).
- **Approvals with no human present** are refused. `file_write` and `file_edit` are in `AUTO_APPROVE`, so a headless deploy can write in its workspace without a human; `workspace_only` still applies. `memory_forget` and `web_fetch` still ask.
- **Memory cleanup** (archive 7 days, purge 30) does not need the scheduler. It runs when the memory store opens, at most every 12 hours (`crates/zeroclaw-memory/src/hygiene.rs`), and the snapshot export runs with it. A daemon that runs for days without a restart may clean up less often; not checked.
- **`config set` spelling** of each path is unverified until the live run, the same as the existing settings.
- **Skill creation with a small local model** may write poor skills. `skills.skill_creation.max_skills` caps the count; the oldest is evicted first.

# Implemented

`zeroclaw/defaults.py` now sets every value above explicitly (42 `config set`
rows, `zeroclaw/helpers.py::_settings`). Deviations from this proposal:

- Sandbox: `risk_profiles.main.sandbox_enabled = true`,
  `risk_profiles.main.sandbox_backend = "docker"`. `SandboxConfig`
  (`security.sandbox`) exists in `schema.rs` but `Config` never references it;
  the sandbox lives on the risk profile. Firejail is not installed. The
  `zeroius-clawius` variant sets `SANDBOX_BACKEND = "none"` for now.
- SOP scope A: `sop.sops_dir = "shared/sops"`,
  `sop.procedural_memory_enabled = true`, and `knowledge` plus the six `sop_*`
  tools are in both `tools.optional` and
  `risk_profiles.main.allowed_tools`.
- `memory.search_mode = "hybrid"` (explicit). With
  `memory.embedding_provider = "none"` there is no embedder, so recall is
  keyword-only; `hybrid` is kept so a later embedding provider is picked up
  without a second change.
- `memory_export` / `memory_purge` stay off.
- `git_operations` is in `ALLOWED_TOOLS` (the proposal left it out for its
  network access). Git commands that write follow the per-agent sandbox, so
  with `SANDBOX_BACKEND = "none"` only `workspace_only` confines them; push
  and pull reach whatever remotes git is configured for.
- `zeroius-clawius` sets `WEB_FETCH_DOMAINS = ["docs.rs", "wiki.archlinux.org",
  "docs.python.org", "github.com"]`, so `web_fetch` is on for those hosts only.
  It is not in `AUTO_APPROVE`, so each fetch asks; with nobody at the
  dashboard it is refused.
- `AUTO_APPROVE` adds `file_write` and `file_edit`, so the agent can write in its
  workspace with nobody at the dashboard (`workspace_only` still applies).
- PATH: the installer runs with `--no-modify-path`, so the deploy adds
  `export PATH="$HOME/.cargo/bin:$PATH"` to `~/.profile` (`files.line`, added
  once). `zeroclaw` then works in an SSH login; the service and the deploy call
  it by its full path.
- API key rotation: the key's sha256 is part of the `.deploy-settings` stamp,
  so a new `LLAMA_API_KEY` re-runs the apply step. The deploy stages the key
  in `~/.zeroclaw/.api-key` (mode 600), and `set_api_key_command` copies it
  into the `api_key` line of `[providers.models.llamacpp.local]` with a short
  `python3` script, then deletes the file. `zeroclaw config set` can't be used:
  it reads secrets only from a terminal (`src/main.rs:230`). ZeroClaw accepts
  a plaintext `api_key` (`crates/zeroclaw-config/src/secrets.rs:289`). If the header
  is missing, the step fails and the next run retries.
