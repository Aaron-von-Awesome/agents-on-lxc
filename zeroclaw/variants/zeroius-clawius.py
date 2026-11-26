from pathlib import Path

from zeroclaw.defaults import *  # shared settings

CONTAINER = "zeroius-clawius"
IMAGE = "ubuntu:26.04"
SSH_USER = "ubuntu"
# no passphrase: pyinfra cannot prompt for one
SSH_KEY_PATH = Path.home() / ".ssh/pyinfra/id_pyinfra"
PUBKEY_PATH = SSH_KEY_PATH.with_name(SSH_KEY_PATH.name + ".pub")

BASE_URL = "http://172.24.1.121:8080/v1"
MODEL = "ornith15"
CONTEXT_LENGTH = 262144
DASHBOARD_PORT = 42617
PROXY_DEVICE = "dashboard"
SANDBOX_BACKEND = "none"  # off while testing ZeroClaw; defaults.py uses docker
WEB_FETCH_DOMAINS = ["docs.rs", "wiki.archlinux.org", "docs.python.org", "github.com"]

# #################################################################################################
# Shared settings come from zeroclaw/defaults.py. To change one for this variant only, uncomment and edit:
# #################################################################################################
#
# ALLOWED_COMMANDS = [*ALLOWED_COMMANDS, "git"]
# ALLOWED_TOOLS = [*ALLOWED_TOOLS, "git_operations"]
# WEB_SEARCH_ENABLED = True
