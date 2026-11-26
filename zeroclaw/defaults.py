"""Settings shared by every ZeroClaw variant. A variant may reassign any of them after `from zeroclaw.defaults import *`."""

RISK_LEVEL = "supervised"
AUTO_APPROVE = [
    "shell",
    "file_read",
    "file_write",
    "file_edit",
    "glob_search",
    "content_search",
    "memory_recall",
    "memory_store",
]
ALLOWED_COMMANDS = ["uname"]
WEB_SEARCH_ENABLED = False
ZEROCLAW_INSTALL_URL = (
    "https://raw.githubusercontent.com/zeroclaw-labs/zeroclaw/master/install.sh"
)

# Hardened minimum
TOOLS_OPTIONAL = [
    "knowledge",
    "sop_list",
    "sop_execute",
    "sop_advance",
    "sop_approve",
    "sop_status",
    "sop_workshop",
]
ALLOWED_TOOLS = [
    "content_search",
    "file_edit",
    "file_read",
    "file_write",
    "git_operations",
    "glob_search",
    "knowledge",
    "memory_forget",
    "memory_recall",
    "memory_store",
    "shell",
    "sop_advance",
    "sop_approve",
    "sop_execute",
    "sop_list",
    "sop_status",
    "sop_workshop",
    "web_fetch",
]
WORKSPACE_ONLY = True
SKILL_CREATION = True
SKILL_IMPROVEMENT = True
WEB_FETCH_DOMAINS = []
HTTP_REQUEST_ENABLED = False
BROWSER_ENABLED = False
MCP_ENABLED = False
SCHEDULER_ENABLED = False
CHECK_UPDATES = False
# "docker" runs each shell command in a throwaway alpine container (launch.py installs the Docker snap
# and enables nesting). "none" turns the OS sandbox off. If Docker is missing, ZeroClaw logs a warning
# and runs unsandboxed.
SANDBOX_BACKEND = "docker"

# Memory and learning, all explicit
MEMORY_BACKEND = "sqlite"
MEMORY_AUTO_SAVE = True
MEMORY_HYGIENE = True
MEMORY_ARCHIVE_AFTER_DAYS = 7
MEMORY_PURGE_AFTER_DAYS = 30
MEMORY_SEARCH_MODE = "hybrid"
MEMORY_EMBEDDING_PROVIDER = "none"
MEMORY_SNAPSHOT = True
MEMORY_SNAPSHOT_ON_HYGIENE = True
MEMORY_EXTRACT_FACTS = True
MEMORY_RESPONSE_CACHE = True
MEMORY_RECALL_LIMIT = 5
KNOWLEDGE_ENABLED = True
SOP_PROCEDURAL_MEMORY = True
SOP_SOPS_DIR = "shared/sops"
