import pytest

import settings
from hermes import helpers as hermes_helpers


def write(root, spec, body):
    p = root / f"{spec.split('/')[0]}" / "variants" / f"{spec.split('/')[1]}.py"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body)


def test_key_env_for():
    assert (
        hermes_helpers.key_env_for("http://172.24.1.121:8080/v1")
        == "HERMES_CUSTOM_172_24_1_121_8080_API_KEY"
    )
    assert (
        hermes_helpers.key_env_for("https://llm.example/v1")
        == "HERMES_CUSTOM_LLM_EXAMPLE_API_KEY"
    )
    assert (
        hermes_helpers.key_env_for("http://u:p@172.24.1.121:8080/v1")
        == "HERMES_CUSTOM_172_24_1_121_8080_API_KEY"
    )
    assert hermes_helpers.key_env_for("") == "HERMES_CUSTOM_API_KEY"


def test_load_variant(tmp_path):
    write(
        tmp_path,
        "hermes/lab",
        'CONTAINER = "lab"\nBASE_URL = "http://h:1/v1"\n_private = 1\n',
    )
    assert settings.load_variant("hermes/lab", tmp_path) == {
        "CONTAINER": "lab",
        "BASE_URL": "http://h:1/v1",
        "AGENT": "hermes",
    }


def test_load_variant_zeroclaw_sets_agent(tmp_path):
    write(tmp_path, "zeroclaw/z", 'CONTAINER = "z"\n')
    assert settings.load_variant("zeroclaw/z", tmp_path)["AGENT"] == "zeroclaw"


@pytest.mark.parametrize(
    "spec",
    [None, "", "lab", "/lab", "hermes/", "hermes/a/b", "nope/lab", "hermes/../settings", "hermes/missing"],
)
def test_load_variant_refuses(tmp_path, spec):
    write(tmp_path, "hermes/lab", "")
    with pytest.raises(RuntimeError, match="hermes/lab"):
        settings.load_variant(spec, tmp_path)


def test_load_variant_ignores_non_agent_folders(tmp_path):
    write(tmp_path, "hermes/lab", 'CONTAINER = "lab"\n')
    write(tmp_path, "nope/x", 'CONTAINER = "lab"\n')
    with pytest.raises(RuntimeError, match="hermes/lab"):
        settings.load_variant("nope/x", tmp_path)
    assert settings.load_variant("hermes/lab", tmp_path)["CONTAINER"] == "lab"


def test_hermius_maximus_values():
    assert settings.AGENT == "hermes"
    assert settings.CONTAINER == "hermius-maximus"
    assert settings.DASHBOARD_PORT == 9119
    assert (
        hermes_helpers.key_env_for(settings.BASE_URL)
        == "HERMES_CUSTOM_172_24_1_121_8080_API_KEY"
    )
    assert settings.PM_EXTRAS == []  # off by default
    assert settings.CLAUDE_CODE is False


@pytest.mark.parametrize(
    "other",
    [
        'CONTAINER = "lab"\nDASHBOARD_PORT = 9120\n',
        'CONTAINER = "other"\nDASHBOARD_PORT = 9119\n',
    ],
)
def test_load_variant_rejects_duplicate(tmp_path, other):
    write(tmp_path, "hermes/lab", 'CONTAINER = "lab"\nDASHBOARD_PORT = 9119\n')
    write(tmp_path, "hermes/old", other)
    with pytest.raises(RuntimeError, match="hermes/old.py"):
        settings.load_variant("hermes/lab", tmp_path)


def test_load_variant_rejects_duplicate_across_agents(tmp_path):
    write(tmp_path, "hermes/h", 'CONTAINER = "h"\nDASHBOARD_PORT = 9119\n')
    write(tmp_path, "zeroclaw/z", 'CONTAINER = "z"\nDASHBOARD_PORT = 9119\n')
    with pytest.raises(
        RuntimeError, match="DASHBOARD_PORT 9119 is also set in hermes/h.py"
    ):
        settings.load_variant("zeroclaw/z", tmp_path)


def test_load_variant_allows_distinct(tmp_path):
    write(tmp_path, "hermes/lab", 'CONTAINER = "lab"\nDASHBOARD_PORT = 9119\n')
    write(tmp_path, "zeroclaw/old", 'CONTAINER = "old"\nDASHBOARD_PORT = 9120\n')
    assert settings.load_variant("hermes/lab", tmp_path)["CONTAINER"] == "lab"


def test_load_variant_ignores_broken_other(tmp_path):
    write(tmp_path, "hermes/lab", 'CONTAINER = "lab"\nDASHBOARD_PORT = 9119\n')
    write(tmp_path, "hermes/bad_import", "import does_not_exist\n")
    write(tmp_path, "zeroclaw/bad_syntax", "CONTAINER = ")
    assert settings.load_variant("hermes/lab", tmp_path)["CONTAINER"] == "lab"


@pytest.mark.parametrize(
    "path",
    sorted(settings.ROOT.glob("*/variants/*.py")),
    ids=lambda p: f"{p.parent.parent.name}/{p.stem}",
)
def test_every_variant_loads(path):
    v = settings.load_variant(f"{path.parent.parent.name}/{path.stem}", settings.ROOT)
    assert v["AGENT"] == path.parent.parent.name and v["CONTAINER"] and v["DASHBOARD_PORT"]
