"""Configuration: environment variables, optionally loaded from a local .env file.

Secrets (API keys, org tokens) are only ever read from the environment / .env,
never from tracked files. .env is git-ignored.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REFERENCE_DIR = ROOT / "reference"
DATA_DIR = ROOT / "data"
WEB_DIR = ROOT / "web"

DEMO_ORG_TOKENS = "org_demo_alpha:alpha-demo-token,org_demo_bravo:bravo-demo-token"


def load_dotenv(path: Path | None = None) -> None:
    """Minimal .env loader (KEY=VALUE lines). Existing env vars win."""
    path = path or ROOT / ".env"
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


@dataclass
class Settings:
    provider: str = "gemini"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.5-flash"
    gemini_fallback_models: list[str] = field(default_factory=list)
    model_timeout_s: float = 90.0
    max_image_side: int = 1600
    var_dir: Path = ROOT / "var"
    host: str = "127.0.0.1"
    port: int = 8000
    org_tokens: dict[str, str] = field(default_factory=dict)  # token -> org_id

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv()
        tokens: dict[str, str] = {}
        for pair in os.environ.get("ORG_TOKENS", DEMO_ORG_TOKENS).split(","):
            if ":" in pair:
                org, tok = pair.split(":", 1)
                if org.strip() and tok.strip():
                    tokens[tok.strip()] = org.strip()
        fallbacks = [m.strip() for m in os.environ.get("GEMINI_FALLBACK_MODELS", "").split(",") if m.strip()]
        var_dir = Path(os.environ.get("VAR_DIR", str(ROOT / "var")))
        if not var_dir.is_absolute():
            var_dir = ROOT / var_dir
        return cls(
            provider=os.environ.get("LLM_PROVIDER", "gemini").strip().lower(),
            gemini_api_key=os.environ.get("GEMINI_API_KEY", "").strip(),
            gemini_model=os.environ.get("GEMINI_MODEL", "gemini-3.5-flash").strip(),
            gemini_fallback_models=fallbacks,
            model_timeout_s=float(os.environ.get("MODEL_TIMEOUT_S", "90")),
            max_image_side=int(os.environ.get("MAX_IMAGE_SIDE", "1600")),
            var_dir=var_dir,
            host=os.environ.get("HOST", "127.0.0.1"),
            port=int(os.environ.get("PORT", "8000")),
            org_tokens=tokens,
        )
