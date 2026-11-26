"""Loads <agent>/variants/<name>.py (from AGENT_VARIANT=<agent>/<name>) into this module, plus AGENT."""

import ast
import os
import runpy
from pathlib import Path

ROOT = Path(__file__).parent
AGENTS = ("hermes", "zeroclaw", "pi")


def _variant_literals(path: Path) -> dict[str, object]:
    # Read only literals: another variant with a broken import must not break this one.
    try:
        tree = ast.parse(path.read_text())
    except SyntaxError, ValueError:
        return {}
    out = {}
    for node in tree.body:
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id in ("CONTAINER", "DASHBOARD_PORT")
        ):
            try:
                out[node.targets[0].id] = ast.literal_eval(node.value)
            except ValueError:
                pass
    return out


def load_variant(spec: str | None, root: Path) -> dict[str, object]:
    paths = [p for a in AGENTS for p in root.glob(f"{a}/variants/*.py")]
    specs = sorted(f"{p.parent.parent.name}/{p.stem}" for p in paths)
    if spec not in specs:
        raise RuntimeError(
            f"Set AGENT_VARIANT to one of: {', '.join(specs)} (got {spec!r})"
        )
    agent, name = spec.split("/")
    path = root / agent / "variants" / f"{name}.py"
    values = {k: v for k, v in runpy.run_path(str(path)).items() if k.isupper()}
    if "DASHBOARD_PORT" in values and not values.get("PROXY_DEVICE"):
        raise RuntimeError(
            f"{spec} sets DASHBOARD_PORT but not PROXY_DEVICE; "
            "the dashboard proxy device needs a name"
        )
    for other in sorted(paths):
        if other == path:
            continue
        theirs = _variant_literals(other)
        for key in ("CONTAINER", "DASHBOARD_PORT"):
            if key in values and theirs.get(key) == values[key]:
                raise RuntimeError(
                    f"{key} {values[key]!r} is also set in {other.parent.parent.name}/{other.name}; each variant needs its own"
                )
    values["AGENT"] = agent
    return values


globals().update(load_variant(os.environ.get("AGENT_VARIANT"), ROOT))
