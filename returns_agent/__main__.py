"""Command line entry point.

  python -m returns_agent serve                      start the operator UI + API
  python -m returns_agent check                      verify the API key / model
  python -m returns_agent inspect --org ORG --order ORDER --images a.jpg b.jpg
  python -m returns_agent eval [--no-cache]          run the evaluation set
  python -m returns_agent findings                   list contradictions in reference data
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

from . import reference
from .config import Settings
from .service import BadRequest, NotFound, ReturnsService
from .store import Store
from .vlm import ModelError, make_provider


def _service(settings: Settings) -> ReturnsService:
    try:
        provider = make_provider(settings)
    except ModelError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(2)
    return ReturnsService(Store(settings.var_dir), provider)


def cmd_check(settings: Settings) -> int:
    print(f"provider: {settings.provider}; model: {settings.gemini_model}; fallbacks: {settings.gemini_fallback_models or 'none'}")
    if settings.provider != "gemini":
        print("Not using Gemini - nothing to check.")
        return 0
    if not settings.gemini_api_key:
        print("GEMINI_API_KEY is empty. Put it in the .env file (see .env.example).")
        return 1
    req = urllib.request.Request("https://generativelanguage.googleapis.com/v1beta/models?pageSize=200",
                                 headers={"x-goog-api-key": settings.gemini_api_key})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            models = json.loads(r.read().decode()).get("models", [])
    except urllib.error.HTTPError as e:
        print(f"Key rejected or API unavailable: HTTP {e.code} {e.read().decode('utf-8', 'replace')[:300]}")
        return 1
    except urllib.error.URLError as e:
        print(f"Network error: {e}")
        return 1
    names = [m["name"].split("/", 1)[-1] for m in models if "generateContent" in m.get("supportedGenerationMethods", [])]
    print("Key OK. Models you can call:")
    for n in names:
        if "flash" in n or "pro" in n:
            print("  ", n)
    wanted = [settings.gemini_model] + settings.gemini_fallback_models
    for w in wanted:
        print(f"{'OK ' if w in names else 'MISSING'}  {w}")
    return 0 if settings.gemini_model in names else 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="returns_agent")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("serve")
    sub.add_parser("check")
    sub.add_parser("findings")
    p = sub.add_parser("inspect")
    p.add_argument("--org", required=True)
    p.add_argument("--order", required=True)
    p.add_argument("--images", nargs="+", required=True)
    p.add_argument("--operator", default="cli_operator")
    p.add_argument("--note", default="")
    e = sub.add_parser("eval")
    e.add_argument("--no-cache", action="store_true")
    e.add_argument("--dir", default=None)
    args = ap.parse_args(argv)
    settings = Settings.from_env()

    if args.cmd == "check":
        return cmd_check(settings)
    if args.cmd == "findings":
        for f in reference.reference_findings():
            print(f"[{f['kind']}] {f['detail']}")
        return 0
    if args.cmd == "serve":
        from .server import serve
        serve(settings, _service(settings))
        return 0
    if args.cmd == "inspect":
        svc = _service(settings)
        try:
            rec = svc.inspect(args.org, args.order, [(Path(i).read_bytes(), None) for i in args.images],
                              args.operator, args.note)
        except (NotFound, BadRequest) as ex:
            print(f"ERROR: {ex}", file=sys.stderr)
            return 1
        print(json.dumps(rec, indent=2))
        print("\n" + rec["outcome"]["summary"], file=sys.stderr)
        return 0
    if args.cmd == "eval":
        from .evaluation import EVAL_DIR, run_eval
        svc = _service(settings)
        report = run_eval(svc.provider, Path(args.dir) if args.dir else EVAL_DIR, use_cache=not args.no_cache)
        print(json.dumps(report, indent=2))
        print(f"\nReport written to {(Path(args.dir) if args.dir else EVAL_DIR) / 'results' / 'report.md'}")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
