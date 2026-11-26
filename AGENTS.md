# Agents on LXC

**Operating manual: [README.md](README.md).** It holds the deploy instructions, operating gotchas and recovery procedures for Hermes, ZeroClaw and Pi. Read it before running or changing any deploy; this file lists only what must stay true of the code.

pyinfra 3.11.2 deploy that builds a Hermes, ZeroClaw or Pi agent container on an LXD host (Ubuntu LXD snap). Run from this directory on the LXD host.

## What must stay true of the code

- Variant files must have unique `CONTAINER` and `DASHBOARD_PORT` across all `*/variants/`, and set `PROXY_DEVICE` whenever `DASHBOARD_PORT` is set; `settings.py` enforces both and names the conflicting file.
- Variant `SSH_KEY_PATH` must have no passphrase: pyinfra cannot prompt for one.
- `CONTEXT_LENGTH` must equal llama-server's per-slot `n_ctx`; `preflight()` also checks `/models`.
- `DASHBOARD_UNIT` is load-bearing: Hermes restarts a user unit with exactly that name after `hermes update`.
- The API key must never reach a command line (`check_api_key` rejects quotes, backslashes and newlines; staging files are 0600).
- Code changes must pass `uv run pytest`; `uv run pyright` typechecks (0 errors expected).
