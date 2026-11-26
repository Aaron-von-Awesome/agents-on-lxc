from pathlib import Path

from pi.defaults import *  # shared settings

CONTAINER = "pious-agenticus"
IMAGE = "ubuntu:26.04"
SSH_USER = "ubuntu"
# no passphrase: pyinfra cannot prompt for one
SSH_KEY_PATH = Path.home() / ".ssh/pyinfra/id_pyinfra"
PUBKEY_PATH = SSH_KEY_PATH.with_name(SSH_KEY_PATH.name + ".pub")

BASE_URL = "http://172.24.1.121:8080/v1"
MODEL = "ornith15"
CONTEXT_LENGTH = 262144

# #################################################################################################
# Shared settings come from pi/defaults.py. To change one for this variant only, uncomment and edit:
# #################################################################################################
#
# THINKING_LEVEL = "high"
