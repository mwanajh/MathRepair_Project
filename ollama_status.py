"""Inspect models exposed by the local Ollama HTTP API."""

import argparse
import json
from urllib import error as url_error
from urllib import request as url_request


def parse_models(payload: dict[str, object]) -> list[dict[str, object]]:
    models = payload.get("models")
    if not isinstance(models, list):
        raise ValueError("Ollama response is missing a models list.")
    return [item for item in models if isinstance(item, dict)]


def fetch_models(base_url: str = "http://localhost:11434") -> list[dict[str, object]]:
    request = url_request.Request(f"{base_url.rstrip('/')}/api/tags")
    try:
        with url_request.urlopen(request, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except url_error.URLError as error:
        raise RuntimeError(
            "Ollama API is unavailable. Start Ollama and try again."
        ) from error
    return parse_models(payload)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://localhost:11434")
    parser.add_argument("--require-model")
    args = parser.parse_args()
    try:
        models = fetch_models(args.base_url)
    except (RuntimeError, ValueError) as error:
        parser.error(str(error))
    names = [str(model.get("name", "")) for model in models]
    print("=== Local Ollama Models ===")
    if not names:
        print("No models installed.")
    for model in models:
        details = model.get("details", {})
        parameter_size = (
            details.get("parameter_size", "unknown")
            if isinstance(details, dict)
            else "unknown"
        )
        print(f"- {model.get('name', 'unknown')} ({parameter_size})")
    if args.require_model:
        if args.require_model not in names:
            parser.error(f"Model is not installed: {args.require_model}")
        print(f"Available: {args.require_model}")


if __name__ == "__main__":
    main()
