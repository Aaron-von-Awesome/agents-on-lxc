import json
import tomllib
from hashlib import sha256
from types import SimpleNamespace

import pytest

import helpers
import zeroclaw.helpers as zc
from zeroclaw import defaults


def ns(**overrides):
    v = {k: x for k, x in vars(defaults).items() if k.isupper()}
    v |= {
        "BASE_URL": "http://172.24.1.121:8080/v1",
        "MODEL": "ornith15",
        "CONTEXT_LENGTH": 262144,
        "DASHBOARD_PORT": 42617,
        "SSH_USER": "ubuntu",
    }
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
    assert p == {
        "uri": s.BASE_URL,
        "model": s.MODEL,
        "context_window": 262144,
        "api_key": "k$#ey",
    }
    assert c["agents"]["main"] == {
        "model_provider": "llamacpp.local",
        "risk_profile": "main",
        "runtime_profile": "main",
        "workspace": {"path": "/home/ubuntu/zeroclaw-workspace"},
    }
    assert c["risk_profiles"]["main"] == {
        "level": "supervised",
        "auto_approve": [
            "shell",
            "file_read",
            "file_write",
            "file_edit",
            "glob_search",
            "content_search",
            "memory_recall",
            "memory_store",
        ],
        "allowed_commands": ["uname"],
        "allowed_tools": defaults.ALLOWED_TOOLS,
        "workspace_only": True,
        "sandbox_enabled": True,
        "sandbox_backend": "docker",
    }
    assert c["runtime_profiles"]["main"] == {"memory_recall_limit": 5}
    assert c["web_search"] == {"enabled": False}
    assert c["gateway"] == {"host": "127.0.0.1", "port": 42617, "check_updates": False}
    assert c["tools"] == {
        "optional": [
            "knowledge",
            "sop_list",
            "sop_execute",
            "sop_advance",
            "sop_approve",
            "sop_status",
            "sop_workshop",
        ]
    }
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
    assert pairs
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
    for name in [
        "knowledge",
        "sop_list",
        "sop_execute",
        "sop_advance",
        "sop_approve",
        "sop_status",
        "sop_workshop",
    ]:
        assert name in optional and name in allowed


def test_apply_settings_commands_do_only_apply():
    cmds = zc.apply_settings_commands("/bin/zc", ns(), "/c.toml", "/k")
    assert len(cmds) == 1 + len(zc.config_set_settings(ns()))
    assert "python3 -c" in cmds[0].get_raw_value()
    assert all("config set --no-interactive" in c.get_raw_value() for c in cmds[1:])
    assert all(".deploy-settings" not in c.get_raw_value() for c in cmds)
    assert all("mv" not in c.get_raw_value() for c in cmds)


def test_stamp_text_records_settings_and_key_hash():
    expected = "".join(f"{p}={v}\n" for p, v in zc.config_set_settings(ns())) + (
        f"api_key_sha256={sha256(b'k').hexdigest()}\n"
    )
    assert zc.stamp_text(ns(), "k") == expected


@pytest.mark.parametrize("old_line", ['api_key = "enc2:abcd"\n', ""])
def test_set_api_key_command_rewrites_only_the_provider_key(tmp_path, old_line):
    import subprocess

    cfg, keyfile = tmp_path / "config.toml", tmp_path / ".api-key"
    text = zc.config_toml(ns(), "old").replace('api_key = "old"\n', old_line)
    cfg.write_text(text + '\n[other]\napi_key = "keep"\n')
    keyfile.write_text("new-key")
    cmd = zc.set_api_key_command(str(cfg), str(keyfile))
    assert "new-key" not in cmd.get_raw_value()
    subprocess.run(["sh", "-c", cmd.get_raw_value()], check=True)
    out = tomllib.loads(cfg.read_text())
    assert out["providers"]["models"]["llamacpp"]["local"]["api_key"] == "new-key"
    assert out["other"]["api_key"] == "keep"
    assert not keyfile.exists() and cfg.stat().st_mode & 0o777 == 0o600


def test_set_api_key_command_fails_clearly_when_table_missing(tmp_path):
    import subprocess

    cfg, keyfile = tmp_path / "config.toml", tmp_path / ".api-key"
    text = 'schema_version = 4\n\n[other]\napi_key = "keep"\n'
    cfg.write_text(text)
    keyfile.write_text("new-key")
    cmd = zc.set_api_key_command(str(cfg), str(keyfile))
    r = subprocess.run(["sh", "-c", cmd.get_raw_value()], capture_output=True, text=True)
    assert r.returncode != 0
    assert "not found in" in r.stderr
    assert keyfile.exists()
    assert cfg.read_text() == text
