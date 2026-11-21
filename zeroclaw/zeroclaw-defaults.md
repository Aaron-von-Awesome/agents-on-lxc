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
| WASM plugins | host built in, but `plugins.enabled = false`, `auto_discover = false`, signature checks `disabled`. None bundled |
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

## Not checked

- The channel, cron, heartbeat and SOP pages were not read in depth.
- Which tools sit behind the remaining "–" risk entries is unconfirmed.

# Proposed hardened minimum

**Goal:** the agent can run tools, remember, and write or improve its own skills, and nothing else. The deploy already sets loopback-only gateway with pairing, a `main` risk profile at `supervised`, `allowed_commands = ["uname"]` and `web_search.enabled = false`. Those stay.

Config paths come from `crates/zeroclaw-config/src/schema.rs` (`#[prefix]` attributes) and `builtin_tools.rs`. None are in `zeroclaw/defaults.py` yet; this is a proposal only.

## Settings

| `defaults.py` name | Value | Config path | Effect |
|---|---|---|---|
| `TOOLS_OPTIONAL` | `[]` | `tools.optional` | Only the 11 core tools are offered. Drops `model_routing_config`, `proxy_config`, cron, browser, SaaS, delegation and the chat helpers. Also shrinks the prompt for the local model |
| `ALLOWED_TOOLS` | `["shell", "file_read", "file_write", "file_edit", "glob_search", "content_search", "memory_recall", "memory_store", "memory_forget", "web_fetch"]` | `risk_profiles.main.allowed_tools` | Closed set for built-ins and MCP. Removes `git_operations` (network) from the core 11. Skill-defined tools stay available |
| `AUTO_APPROVE` | `["shell", "file_read", "file_write", "file_edit", "glob_search", "content_search", "memory_recall", "memory_store"]` | `risk_profiles.main.auto_approve` | Reads, writes and memory writes run unattended. `memory_forget` and `web_fetch` still ask |
| `ALLOWED_COMMANDS` | `["uname"]` (unchanged) | `risk_profiles.main.allowed_commands` | Never add `python`, `node`, `pip`, `npm`, `git` or `cargo`: each one runs any code |
| `WORKSPACE_ONLY` | `True` | `risk_profiles.main.workspace_only` | Set it explicitly; the schema comment and the code disagree on the default |
| `SKILL_CREATION` | `True` | `skills.skill_creation.enabled` | The agent writes a skill after a successful multi-step task. This is the "learn" switch |
| `SKILL_IMPROVEMENT` | `True` | `skills.skill_improvement.enabled` | A post-turn background job patches skills. It builds its own toolset (`skills_list`, `skill_view`, `skill_manage`), so `tools.optional = []` does not block it |
| `WEB_FETCH_DOMAINS` | `[]` | `web_fetch.enabled` = `bool(list)`, `web_fetch.allowed_domains` = list | Off unless a variant names domains, for example `["docs.rs", "wiki.archlinux.org"]` |
| `HTTP_REQUEST_ENABLED` | `False` | `http_request.enabled` | No arbitrary API calls or POSTs |
| `BROWSER_ENABLED` | `False` | `browser.enabled` | Gates `browser_open`. Belt and braces: the tool is already outside the minimal set |
| `MCP_ENABLED` | `False` | `mcp.enabled` | No servers are configured anyway |
| `SCHEDULER_ENABLED` | `False` | `scheduler.enabled` | No cron jobs, no catch-up runs at startup. Skill improvement does not use it |
| `CHECK_UPDATES` | `False` | `gateway.check_updates` | Stops the GitHub poll |
| `SANDBOX_BACKEND` | `"firejail"` | `security.sandbox.enabled` = `true`, `security.sandbox.backend` | The release binary has only firejail and Docker. Needs `apt install firejail` in the deploy |

Left at the default, because the default is already the hardened value:
- `skills.allow_scripts = false`, `skills.open_skills_enabled = false`
- `plugins.enabled = false`
- delegation policy `forbidden`
- heartbeat and SOP off
- sqlite memory with `auto_save` (learning needs it)
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
("security.sandbox.enabled", True),
("security.sandbox.backend", s.SANDBOX_BACKEND),
```

`zeroclaw/deploy.py` also needs `apt.packages(packages=["firejail"])` before the service starts.

## Risks and unverified points

- **Firejail in an unprivileged LXD container** may fail (it needs setuid and user namespaces). What ZeroClaw does when `enabled = true` and the backend fails was not checked. Test it on the live run. If it fails, set `SANDBOX_BACKEND = "none"` on purpose rather than leaving `auto`.
- **Approvals with no human present** are refused. `file_write` and `file_edit` are in `AUTO_APPROVE`, so a headless deploy can write in its workspace without a human; `workspace_only` still applies. `memory_forget` and `web_fetch` still ask.
- **Memory cleanup** (archive 7 days, purge 30) may run on the scheduler. Not checked.
- **`config set` spelling** of each path is unverified until the live run, the same as the existing settings.
- **Skill creation with a small local model** may write poor skills. `skills.skill_creation.max_skills` caps the count; the oldest is evicted first.

# Implemented

`zeroclaw/defaults.py` now sets every value above explicitly (41 `config set`
rows, `zeroclaw/helpers.py::_settings`). Deviations from this proposal:

- Sandbox: `risk_profiles.main.sandbox_enabled = false`,
  `risk_profiles.main.sandbox_backend = "none"`. There is no
  `[security.sandbox]` table in the schema; the sandbox lives on the risk
  profile. Firejail is not installed.
- SOP scope A: `sop.sops_dir = "shared/sops"`,
  `sop.procedural_memory_enabled = true`, and `knowledge` plus the six `sop_*`
  tools are in both `tools.optional` and
  `risk_profiles.main.allowed_tools`.
- `memory.search_mode = "hybrid"` (explicit). With
  `memory.embedding_provider = "none"` there is no embedder, so recall is
  keyword-only; `hybrid` is kept so a later embedding provider is picked up
  without a second change.
- `memory_export` / `memory_purge` stay off.
- `AUTO_APPROVE` adds `file_write` and `file_edit`, so the agent can write in its
  workspace with nobody at the dashboard (`workspace_only` still applies).
