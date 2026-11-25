import json

PROVIDER = "local-llama"


def models_json(s, api_key: str) -> str:
    return json.dumps(
        {"providers": {PROVIDER: {
            "baseUrl": s.BASE_URL, "api": "openai-completions", "apiKey": api_key,
            "models": [{"id": s.MODEL, "contextWindow": s.CONTEXT_LENGTH, "reasoning": True}]}}},
        indent=2,
    ) + "\n"


def settings_json(s) -> str:
    return json.dumps(
        {"defaultProvider": PROVIDER, "defaultModel": s.MODEL,
         "defaultThinkingLevel": s.THINKING_LEVEL, "enableInstallTelemetry": s.INSTALL_TELEMETRY},
        indent=2,
    ) + "\n"
