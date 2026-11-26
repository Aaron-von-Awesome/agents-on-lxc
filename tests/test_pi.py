import json
from types import SimpleNamespace

import pi.helpers as pi
import settings
from pi import defaults


def ns(**overrides):
    v = {k: x for k, x in vars(defaults).items() if k.isupper()}
    v |= {
        "BASE_URL": "http://172.24.1.121:8080/v1",
        "MODEL": "ornith15",
        "CONTEXT_LENGTH": 262144,
    }
    return SimpleNamespace(**(v | overrides))


def test_models_json():
    assert json.loads(pi.models_json(ns(), "k")) == {
        "providers": {
            "local-llama": {
                "baseUrl": "http://172.24.1.121:8080/v1",
                "api": "openai-completions",
                "apiKey": "k",
                "models": [
                    {"id": "ornith15", "contextWindow": 262144, "reasoning": True}
                ],
            }
        }
    }


def test_settings_json():
    assert json.loads(pi.settings_json(ns())) == {
        "defaultProvider": "local-llama",
        "defaultModel": "ornith15",
        "defaultThinkingLevel": "medium",
        "enableInstallTelemetry": False,
    }


def test_variant_loads():
    v = settings.load_variant("pi/pious-agenticus", settings.ROOT)
    assert v["CONTAINER"] == "pious-agenticus" and v["AGENT"] == "pi"
    assert "DASHBOARD_PORT" not in v and "PROXY_DEVICE" not in v
