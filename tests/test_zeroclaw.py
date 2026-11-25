import json
import tomllib
from types import SimpleNamespace

import pytest

import helpers
import zeroclaw.defaults as defaults
import zeroclaw.helpers as zc


def ns(**overrides):
    v = {k: x for k, x in vars(defaults).items() if k.isupper()}
    v |= dict(
        BASE_URL="http://172.24.1.121:8080/v1",
        MODEL="ornith15",
        CONTEXT_LENGTH=262144,
        DASHBOARD_PORT=42617,
        SSH_USER="ubuntu",
    )
    return SimpleNamespace(**(v | overrides))


@pytest.mark.parametrize("bad", ["a'b", 'a"b', "a\\b", "a\nb", "a\rb"])
def test_check_api_key_rejects(bad):
    with pytest.raises(ValueError):
        helpers.check_api_key(bad)


def test_check_api_key_returns_key():
    assert helpers.check_api_key("k$#ey") == "k$#ey"


def test_config_toml_round_trips():
    s = ns(MODEL='orn"ith#15', BASE_URL="http://172.24.1.121:8080/v1")
    text = zc.config_toml(s, "k$#ey")
    assert text.splitlines()[0] == "schema_version = 4"
    c = tomllib.loads(text)
    p = c["providers"]["models"]["llamacpp"]["local"]
    assert p == {"uri": s.BASE_URL, "model": s.MODEL, "context_window": 262144, "api_key": "k$#ey"}
    assert c["agents"]["main"] == {
        "model_provider": "llamacpp.local",
        "risk_profile": "main",
        "runtime_profile": "main",
        "workspace": {"path": "/home/ubuntu/zeroclaw-workspace"},
    }
    assert c["risk_profiles"]["main"] == {
        "level": "supervised",
        "auto_approve": ["shell", "file_read", "file_write", "file_edit", "glob_search", "content_search", "memory_recall", "memory_store"],
        "allowed_commands": ["uname"],
        "allowed_tools": [
            "shell", "file_read", "file_write", "file_edit", "glob_search", "content_search",
            "memory_recall", "memory_store", "memory_forget", "web_fetch",
            "knowledge", "sop_list", "sop_execute", "sop_advance", "sop_approve", "sop_status", "sop_workshop",
        ],
        "workspace_only": True,
        "sandbox_enabled": True,
        "sandbox_backend": "docker",
    }
    assert c["runtime_profiles"]["main"] == {"memory_recall_limit": 5}
    assert c["web_search"] == {"enabled": False}
    assert c["gateway"] == {"host": "127.0.0.1", "port": 42617, "check_updates": False}
    assert c["tools"] == {"optional": [
        "knowledge", "sop_list", "sop_execute", "sop_advance", "sop_approve", "sop_status", "sop_workshop",
    ]}
    assert c["skills"]["skill_creation"] == {"enabled": True}
    assert c["skills"]["skill_improvement"] == {"enabled": True}
    assert c["web_fetch"] == {"enabled": False, "allowed_domains": ["*"]}
    assert c["http_request"] == {"enabled": False}
    assert c["browser"] == {"enabled": False}
    assert c["mcp"] == {"enabled": False}
    assert c["scheduler"] == {"enabled": False}
    assert c["memory"] == {
        "backend": "sqlite",
        "auto_save": True,
        "hygiene_enabled": True,
        "archive_after_days": 7,
        "purge_after_days": 30,
        "search_mode": "hybrid",
        "embedding_provider": "none",
        "snapshot_enabled": True,
        "snapshot_on_hygiene": True,
        "consolidation_extract_facts": True,
        "response_cache_enabled": True,
    }
    assert c["knowledge"] == {"enabled": True}
    assert c["sop"] == {"procedural_memory_enabled": True, "sops_dir": "shared/sops"}


def test_config_set_settings_has_no_key_and_binds_loopback():
    pairs = zc.config_set_settings(ns())
    d = dict(pairs)
    assert d["gateway.host"] == "127.0.0.1" and d["gateway.port"] == "42617"
    assert d["risk_profiles.main.allowed_commands"] == '["uname"]'
    assert d["risk_profiles.main.sandbox_enabled"] == "true"
    assert d["risk_profiles.main.sandbox_backend"] == "docker"
    off = dict(zc.config_set_settings(ns(SANDBOX_BACKEND="none")))
    assert off["risk_profiles.main.sandbox_enabled"] == "false"
    assert all("api_key" not in p for p, _ in pairs)


def test_config_toml_matches_config_set_settings():  # one source of truth
    s = ns()
    c = tomllib.loads(zc.config_toml(s, "k"))
    pairs = zc.config_set_settings(s)
    assert len(pairs) == 42
    for path, value in pairs:
        node = c
        for part in path.split("."):  # the alias llamacpp.local is two table levels
            node = node[part]
        assert (node if isinstance(node, str) else json.dumps(node)) == value


def test_sandbox_uses_risk_profile_not_security_section():
    c = tomllib.loads(zc.config_toml(ns(), "k"))
    assert "sandbox" not in c.get("security", {})
    assert c["risk_profiles"]["main"]["sandbox_backend"] == "docker"


def test_feature_tools_are_optional_and_allowed():
    d = dict(zc.config_set_settings(ns()))
    optional = json.loads(d["tools.optional"])
    allowed = json.loads(d["risk_profiles.main.allowed_tools"])
    for name in ["knowledge", "sop_list", "sop_execute", "sop_advance", "sop_approve", "sop_status", "sop_workshop"]:
        assert name in optional and name in allowed


def test_settings_move_aside_first_and_commit_after_the_restart():
    binary = "/home/u/.cargo/bin/zeroclaw"
    unit = "zeroclaw.service"
    stamp = "/home/u/.zeroclaw/.deploy-settings"
    pending = stamp + ".pending"
    apply_cmds = zc.apply_settings_commands(binary, ns(), stamp, pending)
    restart_cmds = zc.restart_commands(unit, stamp, pending)
    # The stamp moves aside before anything is applied, so a failure leaves .pending.
    assert len(apply_cmds) == 1 + len(zc.config_set_settings(ns()))
    assert "mv" in apply_cmds[0].get_raw_value()
    assert stamp in apply_cmds[0].get_raw_value() and pending in apply_cmds[0].get_raw_value()
    assert all("config set --no-interactive" in c.get_raw_value() for c in apply_cmds[1:])
    # The commit is last, and only after the restart.
    assert "restart" in restart_cmds[0].get_raw_value()
    assert "mv" not in restart_cmds[0].get_raw_value()
    assert len(restart_cmds) == 2
    assert "mv" in restart_cmds[1].get_raw_value()
    assert pending in restart_cmds[1].get_raw_value() and stamp in restart_cmds[1].get_raw_value()
