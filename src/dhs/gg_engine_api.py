from __future__ import annotations

import json
import base64
import subprocess
from pathlib import Path
from typing import Callable

from .models import Action


PROJECT_ROOT = Path(__file__).resolve().parents[2]
REQUEST_SCRIPT = PROJECT_ROOT / "tools" / "gg_engine_request.ps1"
CORE_PROPS = Path(r"C:\ProgramData\SteelSeries\GG\coreProps.json")


class GGEngineError(RuntimeError):
    pass


def actions_to_api_events(actions: list[Action]) -> list[dict]:
    """Create the event shape used by GG 119's own macro editor API."""
    result: list[dict] = []
    previous = 0
    for action in sorted(actions, key=lambda item: item.time_ms):
        delay = action.time_ms - previous
        if delay < 0:
            raise ValueError("negative delay")
        if delay:
            result.append(
                {"type": 4, "page": 0, "code": 0, "extraData": delay, "timestamp": 0}
            )
        result.append(
            {
                "type": 2 if action.kind == "keyboard" else 0,
                "page": 1 if action.kind == "keyboard" else 0,
                "code": action.code,
                "extraData": 1 if action.down else 0,
                "timestamp": 0,
            }
        )
        previous = action.time_ms
    return result


def _run_request(method: str, path: str, payload: dict | None = None) -> dict:
    if not REQUEST_SCRIPT.is_file():
        raise GGEngineError(f"GG request helper is missing: {REQUEST_SCRIPT}")
    if not CORE_PROPS.is_file():
        raise GGEngineError("SteelSeries GG is not running (coreProps.json is unavailable).")
    command = [
        "powershell.exe",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(REQUEST_SCRIPT),
        "-Method",
        method,
        "-Path",
        path,
        "-CorePropsPath",
        str(CORE_PROPS),
    ]
    body = "" if payload is None else json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    completed = subprocess.run(
        command,
        input=body.encode("utf-8"),
        capture_output=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        timeout=20,
        check=False,
    )
    output = completed.stdout.decode("utf-8-sig", errors="replace").strip()
    try:
        envelope = json.loads(output)
    except json.JSONDecodeError as exc:
        detail = completed.stderr.decode("utf-8-sig", errors="replace").strip() or output or f"exit code {completed.returncode}"
        raise GGEngineError(f"GG Engine request failed: {detail}") from exc
    if not envelope.get("ok"):
        raise GGEngineError(
            f"GG Engine request failed ({envelope.get('status', 0)}): {envelope.get('reason', 'unknown error')}"
        )
    response_body_base64 = envelope.get("bodyBase64", "")
    if not response_body_base64:
        return {}
    try:
        response_body = base64.b64decode(response_body_base64).decode("utf-8")
        result = json.loads(response_body)
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GGEngineError("GG Engine returned an invalid JSON response.") from exc
    if isinstance(result, dict) and "error" in result:
        error = result["error"]
        message = error.get("message", "unknown error") if isinstance(error, dict) else str(error)
        raise GGEngineError(f"GG Engine rejected the request: {message}")
    return result


def list_macros(request: Callable = _run_request) -> list[dict]:
    response = request("GET", "macros")
    macros = response.get("macros")
    if not isinstance(macros, list):
        raise GGEngineError("GG Engine returned an invalid macro list.")
    return macros


def validate_macro_name(name: str, request: Callable = _run_request) -> None:
    response = request("POST", "macro/validate", {"id": 0, "name": name})
    validation = response.get("macroValidation", {})
    problems = validation.get("nameValidations", [])
    if problems:
        raise GGEngineError(f"GG rejected the macro name: {', '.join(map(str, problems))}")


def create_macro(
    name: str,
    events: list[dict],
    request: Callable = _run_request,
) -> str:
    clean_name = name.strip()
    if not clean_name:
        raise ValueError("macro name cannot be empty")
    if not events:
        raise ValueError("macro events cannot be empty")
    validate_macro_name(clean_name, request=request)
    payload = {
        "name": clean_name,
        "events": json.dumps(events, ensure_ascii=False, separators=(",", ":")),
        "recordingOptions": json.dumps(
            {"delay": 15, "delayState": 0}, separators=(",", ":")
        ),
    }
    response = request("POST", "macro", payload)
    macro_id = response.get("macro_id")
    if not isinstance(macro_id, str) or not macro_id:
        raise GGEngineError("GG Engine did not return the new macro ID.")
    return macro_id
