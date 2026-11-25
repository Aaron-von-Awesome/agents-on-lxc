"""Settings shared by every Pi variant. A variant may reassign any of them after `from pi.defaults import *`."""

NODE_SNAP_CHANNEL = "26/stable"  # snap channel for Node, which Pi's installer needs
PI_INSTALL_URL = "https://pi.dev/install.sh"  # Pi installer script
INSTALL_TELEMETRY = False  # settings.json enableInstallTelemetry
THINKING_LEVEL = "medium"  # settings.json defaultThinkingLevel
