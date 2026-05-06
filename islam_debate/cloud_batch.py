from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import requests

from islam_debate.prompts import (
    build_conclusion_prompt,
    build_opening_prompt,
    build_response_prompt,
    opening_history_entry,
    opponent_history_entry,
    response_history_entry,
)
from islam_debate.topics import TOPICS
from islam_debate.utils import save_json

logger = logging.getLogger(__name__)

STEP_ORDER = [
    "opening_for",
    "opening_against",
    "response_for",
    "response_against",
    "conclusion_for",
    "conclusion_against",
]
OPENAI_BASE_URL = "https://api.openai.com/v1"
ANTHROPIC_BASE_URL = "https://api.anthropic.com/v1"
ANTHROPIC_VERSION = "2023-06-01"
OPENAI_ENDPOINT = "/v1/chat/completions"
OPENAI_TERMINAL_FAILURES = {"failed", "expired", "cancelled"}


def now_utc_iso() -> str:
    return datetime.now(UTC).isoformat()


def slugify(value: str) -> str:
    slug = value.lower()
    slug = re.sub(r"[^a-z0-9]+", "_", slug)
    return slug.strip("_")


def load_env_file(path: str | None) -> None:
    if not path:
        return

    env_path = Path(path)
    if not env_path.exists():
        raise FileNotFoundError(f"Env file not found: {env_path}")

    for raw_line in env_path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key.startswith("export "):
            key = key.removeprefix("export ").strip()
        value = value.strip().strip("'").strip('"')
        os.environ.setdefault(key, value)


def _debate_id(provider: str, model: str, run_label: str, topic: str) -> str:
    return f"{provider}__{slugify(model)}__{run_label}__{slugify(topic)}"


def _output_stem(topic: str, model: str, run_label: str) -> str:
    return f"{slugify(topic)}__{slugify(model)}__{run_label}"


def _request_custom_id(debate_id: str, step: str) -> str:
    digest = hashlib.sha1(f"{debate_id}::{step}".encode()).hexdigest()[:20]
    return f"req_{digest}"


def initialize_state(
    state_dir: Path,
    openai_model: str,
    anthropic_model: str,
    openai_runs: int,
    anthropic_runs: int,
    openai_run_start: int,
    anthropic_run_start: int,
) -> dict[str, Any]:
    state = {
        "schema_version": 1,
        "created_at": now_utc_iso(),
        "updated_at": now_utc_iso(),
        "state_dir": str(state_dir),
        "output_dir": str(state_dir / "results"),
        "config": {
            "openai_model": openai_model,
            "anthropic_model": anthropic_model,
            "openai_runs": openai_runs,
            "anthropic_runs": anthropic_runs,
            "openai_run_start": openai_run_start,
            "anthropic_run_start": anthropic_run_start,
            "num_rounds": 1,
        },
        "batches": [],
        "debates": [],
    }

    for run_index in range(openai_run_start, openai_run_start + openai_runs):
        run_label = f"run{run_index:02d}"
        for topic in TOPICS:
            state["debates"].append(
                _new_debate_record(
                    provider="openai",
                    model=openai_model,
                    run_label=run_label,
                    topic=topic,
                )
            )

    for run_index in range(
        anthropic_run_start,
        anthropic_run_start + anthropic_runs,
    ):
        run_label = f"run{run_index:02d}"
        for topic in TOPICS:
            state["debates"].append(
                _new_debate_record(
                    provider="anthropic",
                    model=anthropic_model,
                    run_label=run_label,
                    topic=topic,
                )
            )

    return state


def _new_debate_record(
    provider: str,
    model: str,
    run_label: str,
    topic: str,
) -> dict[str, Any]:
    return {
        "id": _debate_id(provider, model, run_label, topic),
        "provider": provider,
        "llm_type": provider,
        "model": model,
        "run_label": run_label,
        "topic": topic,
        "started_at": None,
        "completed_at": None,
        "steps": {step: None for step in STEP_ORDER},
        "output_stem": _output_stem(topic, model, run_label),
    }


def load_state(state_dir: Path) -> dict[str, Any]:
    state_path = state_dir / "state.json"
    if not state_path.exists():
        raise FileNotFoundError(f"State file not found: {state_path}")
    return json.loads(state_path.read_text())


def save_state(state_dir: Path, state: dict[str, Any]) -> None:
    state["updated_at"] = now_utc_iso()
    state_dir.mkdir(parents=True, exist_ok=True)
    state_path = state_dir / "state.json"
    state_path.write_text(json.dumps(state, indent=2))


def find_debate(state: dict[str, Any], debate_id: str) -> dict[str, Any]:
    for debate in state["debates"]:
        if debate["id"] == debate_id:
            return debate
    raise KeyError(f"Unknown debate id: {debate_id}")


def pending_requests_for_debate(state: dict[str, Any], debate_id: str) -> set[str]:
    pending: set[str] = set()
    for batch in state["batches"]:
        if batch["status"] not in {"submitted", "processing"}:
            continue
        for request in batch["requests"]:
            if request["debate_id"] == debate_id:
                pending.add(request["step"])
    return pending


def is_debate_complete(debate: dict[str, Any]) -> bool:
    return all(debate["steps"].get(step) for step in STEP_ORDER)


def debate_history_for_step(debate: dict[str, Any], step: str) -> list[str]:
    if step == "response_for":
        return [
            opening_history_entry("for", debate["steps"]["opening_for"]),
            opponent_history_entry(debate["steps"]["opening_against"]),
        ]
    if step == "response_against":
        return [
            opening_history_entry("against", debate["steps"]["opening_against"]),
            opponent_history_entry(debate["steps"]["response_for"]),
        ]
    if step == "conclusion_for":
        return [
            opening_history_entry("for", debate["steps"]["opening_for"]),
            opponent_history_entry(debate["steps"]["opening_against"]),
            response_history_entry("for", debate["steps"]["response_for"]),
        ]
    if step == "conclusion_against":
        return [
            opening_history_entry("against", debate["steps"]["opening_against"]),
            opponent_history_entry(debate["steps"]["response_for"]),
            response_history_entry("against", debate["steps"]["response_against"]),
        ]
    return []


def build_prompt_for_step(debate: dict[str, Any], step: str) -> str:
    topic = debate["topic"]
    if step == "opening_for":
        return build_opening_prompt(topic, "for")
    if step == "opening_against":
        return build_opening_prompt(topic, "against")
    if step == "response_for":
        return build_response_prompt(
            topic,
            "for",
            debate_history_for_step(debate, step),
        )
    if step == "response_against":
        return build_response_prompt(
            topic,
            "against",
            debate_history_for_step(debate, step),
        )
    if step == "conclusion_for":
        return build_conclusion_prompt(
            topic,
            "for",
            debate_history_for_step(debate, step),
        )
    if step == "conclusion_against":
        return build_conclusion_prompt(
            topic,
            "against",
            debate_history_for_step(debate, step),
        )
    raise ValueError(f"Unknown step: {step}")


def ready_steps_for_debate(state: dict[str, Any], debate: dict[str, Any]) -> list[str]:
    pending = pending_requests_for_debate(state, debate["id"])
    ready: list[str] = []

    if not debate["steps"]["opening_for"] and "opening_for" not in pending:
        ready.append("opening_for")
    if not debate["steps"]["opening_against"] and "opening_against" not in pending:
        ready.append("opening_against")
    if (
        debate["steps"]["opening_against"]
        and not debate["steps"]["response_for"]
        and "response_for" not in pending
    ):
        ready.append("response_for")
    if (
        debate["steps"]["response_for"]
        and not debate["steps"]["response_against"]
        and "response_against" not in pending
    ):
        ready.append("response_against")
    if (
        debate["steps"]["response_for"]
        and not debate["steps"]["conclusion_for"]
        and "conclusion_for" not in pending
    ):
        ready.append("conclusion_for")
    if (
        debate["steps"]["response_against"]
        and not debate["steps"]["conclusion_against"]
        and "conclusion_against" not in pending
    ):
        ready.append("conclusion_against")

    return ready


def collect_ready_requests(
    state: dict[str, Any],
    provider: str,
    max_requests: int | None,
) -> list[dict[str, Any]]:
    collected: list[dict[str, Any]] = []
    for debate in state["debates"]:
        if debate["provider"] != provider:
            continue
        for step in ready_steps_for_debate(state, debate):
            collected.append(
                {
                    "custom_id": _request_custom_id(debate["id"], step),
                    "debate_id": debate["id"],
                    "step": step,
                    "prompt": build_prompt_for_step(debate, step),
                }
            )
            if max_requests and len(collected) >= max_requests:
                return collected
    return collected


def openai_headers() -> dict[str, str]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable not set")
    return {"Authorization": f"Bearer {api_key}"}


def anthropic_headers() -> dict[str, str]:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable not set")
    return {
        "x-api-key": api_key,
        "anthropic-version": ANTHROPIC_VERSION,
        "content-type": "application/json",
    }


def _ensure_complete_results(
    batch: dict[str, Any],
    parsed: dict[str, dict[str, Any]],
    failed: dict[str, dict[str, Any]] | None = None,
) -> None:
    expected_ids = {request["custom_id"] for request in batch["requests"]}
    observed_ids = set(parsed.keys())
    if failed:
        observed_ids |= set(failed.keys())
    missing_ids = sorted(expected_ids - observed_ids)
    if missing_ids:
        raise RuntimeError(
            "Batch results were incomplete for "
            f"{batch['provider']} batch {batch['id']}: missing {missing_ids[:5]}"
        )


def _download_openai_file(file_id: str) -> list[dict[str, Any]]:
    response = requests.get(
        f"{OPENAI_BASE_URL}/files/{file_id}/content",
        headers=openai_headers(),
        timeout=120,
    )
    response.raise_for_status()
    return [
        json.loads(line)
        for line in response.text.splitlines()
        if line.strip()
    ]


def _extract_openai_error(item: dict[str, Any]) -> dict[str, Any]:
    response = item.get("response") or {}
    body = response.get("body") or {}
    error = body.get("error") or item.get("error") or {}
    return {
        "status_code": response.get("status_code"),
        "type": error.get("type"),
        "code": error.get("code"),
        "message": error.get("message"),
        "raw": item,
    }


def _openai_quota_blocked(state: dict[str, Any]) -> bool:
    for batch in state["batches"]:
        if batch["provider"] != "openai":
            continue
        for failure in batch.get("request_failures", []):
            if failure.get("code") == "insufficient_quota":
                return True
    return False


def submit_openai_batch(
    state_dir: Path,
    model: str,
    requests_to_submit: list[dict[str, Any]],
) -> dict[str, Any]:
    batch_dir = state_dir / "openai_batches"
    batch_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    payload_path = batch_dir / f"{timestamp}.jsonl"

    with payload_path.open("w") as fh:
        for request in requests_to_submit:
            body = {
                "model": model,
                "messages": [{"role": "user", "content": request["prompt"]}],
            }
            fh.write(
                json.dumps(
                    {
                        "custom_id": request["custom_id"],
                        "method": "POST",
                        "url": OPENAI_ENDPOINT,
                        "body": body,
                    }
                )
                + "\n"
            )

    with payload_path.open("rb") as fh:
        upload = requests.post(
            f"{OPENAI_BASE_URL}/files",
            headers=openai_headers(),
            data={"purpose": "batch"},
            files={"file": (payload_path.name, fh, "application/jsonl")},
            timeout=120,
        )
    upload.raise_for_status()
    file_id = upload.json()["id"]

    batch = requests.post(
        f"{OPENAI_BASE_URL}/batches",
        headers={**openai_headers(), "Content-Type": "application/json"},
        json={
            "input_file_id": file_id,
            "endpoint": OPENAI_ENDPOINT,
            "completion_window": "24h",
            "metadata": {"source": "islam-debate-cloud-batch"},
        },
        timeout=120,
    )
    if not batch.ok:
        raise RuntimeError(
            "OpenAI batch creation failed: "
            f"{batch.status_code} {batch.text}"
        )
    batch_json = batch.json()

    return {
        "provider": "openai",
        "id": batch_json["id"],
        "status": "submitted",
        "submitted_at": now_utc_iso(),
        "requests": [
            {
                "custom_id": request["custom_id"],
                "debate_id": request["debate_id"],
                "step": request["step"],
            }
            for request in requests_to_submit
        ],
        "input_path": str(payload_path),
        "input_file_id": file_id,
        "raw": batch_json,
    }


def submit_anthropic_batch(
    model: str,
    requests_to_submit: list[dict[str, Any]],
) -> dict[str, Any]:
    payload = {
        "requests": [
            {
                "custom_id": request["custom_id"],
                "params": {
                    "model": model,
                    "max_tokens": 1000,
                    "messages": [{"role": "user", "content": request["prompt"]}],
                },
            }
            for request in requests_to_submit
        ]
    }

    response = requests.post(
        f"{ANTHROPIC_BASE_URL}/messages/batches",
        headers=anthropic_headers(),
        json=payload,
        timeout=120,
    )
    if not response.ok:
        raise RuntimeError(
            "Anthropic batch creation failed: "
            f"{response.status_code} {response.text}"
        )
    batch_json = response.json()

    return {
        "provider": "anthropic",
        "id": batch_json["id"],
        "status": "submitted",
        "submitted_at": now_utc_iso(),
        "requests": [
            {
                "custom_id": request["custom_id"],
                "debate_id": request["debate_id"],
                "step": request["step"],
            }
            for request in requests_to_submit
        ],
        "raw": batch_json,
    }


def poll_openai_batch(batch: dict[str, Any]) -> dict[str, Any]:
    response = requests.get(
        f"{OPENAI_BASE_URL}/batches/{batch['id']}",
        headers=openai_headers(),
        timeout=120,
    )
    response.raise_for_status()
    batch_json = response.json()
    status = batch_json["status"]
    if status in OPENAI_TERMINAL_FAILURES:
        raise RuntimeError(
            f"OpenAI batch {batch['id']} ended with status {status}: "
            f"{batch_json.get('errors')}"
        )
    if status != "completed":
        batch["status"] = "processing"
        batch["raw"] = batch_json
        return {}

    parsed: dict[str, dict[str, Any]] = {}
    failed: dict[str, dict[str, Any]] = {}

    output_file_id = batch_json.get("output_file_id")
    if output_file_id:
        for item in _download_openai_file(output_file_id):
            custom_id = item["custom_id"]
            if item.get("error"):
                failed[custom_id] = _extract_openai_error(item)
                continue
            body = item["response"]["body"]
            message = body["choices"][0]["message"]["content"]
            if isinstance(message, list):
                text = "".join(
                    part.get("text", "")
                    for part in message
                    if part.get("type") == "text"
                )
            else:
                text = message
            parsed[custom_id] = {"text": text, "usage": body.get("usage")}

    error_file_id = batch_json.get("error_file_id")
    if error_file_id:
        for item in _download_openai_file(error_file_id):
            failed[item["custom_id"]] = _extract_openai_error(item)

    _ensure_complete_results(batch, parsed, failed)
    batch["status"] = "completed"
    batch["completed_at"] = now_utc_iso()
    batch["raw"] = batch_json
    batch["request_failures"] = [
        {"custom_id": custom_id, **details}
        for custom_id, details in sorted(failed.items())
    ]
    return parsed


def poll_anthropic_batch(batch: dict[str, Any]) -> dict[str, dict[str, Any]]:
    response = requests.get(
        f"{ANTHROPIC_BASE_URL}/messages/batches/{batch['id']}",
        headers=anthropic_headers(),
        timeout=120,
    )
    response.raise_for_status()
    batch_json = response.json()
    if batch_json["processing_status"] != "ended":
        batch["status"] = "processing"
        batch["raw"] = batch_json
        return {}

    results_url = batch_json.get("results_url")
    if not results_url:
        raise RuntimeError(
            f"Anthropic batch ended without results URL: {batch['id']}"
        )

    results = requests.get(results_url, headers=anthropic_headers(), timeout=120)
    results.raise_for_status()

    parsed: dict[str, dict[str, Any]] = {}
    for line in results.text.splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        custom_id = item["custom_id"]
        result = item["result"]
        if result["type"] != "succeeded":
            raise RuntimeError(f"Anthropic batch request failed: {custom_id}: {result}")
        text = "".join(
            part.get("text", "")
            for part in result["message"]["content"]
            if part.get("type") == "text"
        )
        parsed[custom_id] = {"text": text, "usage": result["message"].get("usage")}

    _ensure_complete_results(batch, parsed)
    batch["status"] = "completed"
    batch["completed_at"] = now_utc_iso()
    batch["raw"] = batch_json
    return parsed


def apply_batch_results(
    state: dict[str, Any],
    batch: dict[str, Any],
    results: dict[str, Any],
) -> None:
    request_map = {
        request["custom_id"]: request
        for request in batch["requests"]
    }
    for custom_id, payload in results.items():
        request = request_map[custom_id]
        debate = find_debate(state, request["debate_id"])
        if debate["started_at"] is None:
            debate["started_at"] = batch["submitted_at"]
        debate["steps"][request["step"]] = payload["text"]
        if is_debate_complete(debate) and debate["completed_at"] is None:
            debate["completed_at"] = batch.get("completed_at", now_utc_iso())


def poll_batches(state: dict[str, Any]) -> None:
    for batch in state["batches"]:
        if batch["status"] == "completed":
            continue
        if batch["provider"] == "openai":
            results = poll_openai_batch(batch)
        else:
            results = poll_anthropic_batch(batch)
        if results:
            apply_batch_results(state, batch, results)


def submit_ready_batches(
    state_dir: Path,
    state: dict[str, Any],
    openai_max_requests: int | None,
    anthropic_max_requests: int | None,
    retry_openai_failures: bool,
) -> int:
    submitted = 0
    active_providers = {
        batch["provider"]
        for batch in state["batches"]
        if batch["status"] in {"submitted", "processing"}
    }

    if (
        "openai" not in active_providers
        and (retry_openai_failures or not _openai_quota_blocked(state))
    ):
        requests_to_submit = collect_ready_requests(
            state,
            "openai",
            openai_max_requests,
        )
        if requests_to_submit:
            batch = submit_openai_batch(
                state_dir,
                state["config"]["openai_model"],
                requests_to_submit,
            )
            state["batches"].append(batch)
            submitted += 1

    if "anthropic" not in active_providers:
        requests_to_submit = collect_ready_requests(
            state,
            "anthropic",
            anthropic_max_requests,
        )
        if requests_to_submit:
            batch = submit_anthropic_batch(
                state["config"]["anthropic_model"],
                requests_to_submit,
            )
            state["batches"].append(batch)
            submitted += 1

    return submitted


def materialize_completed_debates(state: dict[str, Any]) -> int:
    output_dir = Path(state["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)
    written = 0

    for debate in state["debates"]:
        if not is_debate_complete(debate):
            continue

        output_base = output_dir / debate["output_stem"]
        output_path = output_base.with_suffix(".json")
        if output_path.exists():
            continue

        started_at = debate["started_at"]
        completed_at = debate["completed_at"]
        time_taken = None
        if started_at and completed_at:
            start_dt = datetime.fromisoformat(started_at)
            end_dt = datetime.fromisoformat(completed_at)
            time_taken = (end_dt - start_dt).total_seconds()

        payload = {
            "metadata": {
                "model": debate["model"],
                "topic": debate["topic"],
                "llm_type": debate["llm_type"],
                "num_rounds": 1,
                "date": completed_at or now_utc_iso(),
                "time_taken": time_taken,
                "run_label": debate["run_label"],
            },
            "debate": {
                "opening_arguments": {
                    "for": debate["steps"]["opening_for"],
                    "against": debate["steps"]["opening_against"],
                },
                "round_1": {
                    "for": debate["steps"]["response_for"],
                    "against": debate["steps"]["response_against"],
                },
                "conclusions": {
                    "for": debate["steps"]["conclusion_for"],
                    "against": debate["steps"]["conclusion_against"],
                },
            },
        }
        save_json(payload, str(output_base))
        written += 1

    return written


def summarize_state(state: dict[str, Any]) -> str:
    completed = sum(1 for debate in state["debates"] if is_debate_complete(debate))
    total = len(state["debates"])
    by_model: dict[str, int] = {}
    for debate in state["debates"]:
        key = f"{debate['model']} ({debate['provider']})"
        by_model.setdefault(key, 0)
        if is_debate_complete(debate):
            by_model[key] += 1

    lines = [f"Completed debates: {completed}/{total}"]
    for key in sorted(by_model):
        expected = sum(
            1
            for debate in state["debates"]
            if f"{debate['model']} ({debate['provider']})" == key
        )
        lines.append(f"- {key}: {by_model[key]}/{expected}")

    active_batches = [
        batch
        for batch in state["batches"]
        if batch["status"] in {"submitted", "processing"}
    ]
    if active_batches:
        lines.append("Active batches:")
        for batch in active_batches:
            lines.append(
                f"- {batch['provider']} {batch['id']} "
                f"({len(batch['requests'])} requests, {batch['status']})"
            )
    if _openai_quota_blocked(state):
        failed_requests = sum(
            1
            for batch in state["batches"]
            if batch["provider"] == "openai"
            for failure in batch.get("request_failures", [])
            if failure.get("code") == "insufficient_quota"
        )
        lines.append(
            "OpenAI is blocked by insufficient quota "
            f"({failed_requests} request(s) failed with insufficient_quota)."
        )
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run cloud debate reruns through OpenAI Batch API and "
            "Anthropic Message Batches."
        )
    )
    parser.add_argument(
        "command",
        choices=["advance", "status"],
        nargs="?",
        default="advance",
    )
    parser.add_argument("--env-file", default=None, help="Path to a .env file")
    parser.add_argument(
        "--state-dir",
        default="islam_debate/data/cloud_batch_20260430",
        help="Directory used to store batch state and generated results",
    )
    parser.add_argument("--openai-model", default="gpt-5.5")
    parser.add_argument("--anthropic-model", default="claude-opus-4-7")
    parser.add_argument("--openai-runs", type=int, default=10)
    parser.add_argument("--anthropic-runs", type=int, default=1)
    parser.add_argument("--openai-run-start", type=int, default=1)
    parser.add_argument("--anthropic-run-start", type=int, default=1)
    parser.add_argument("--openai-max-requests", type=int, default=None)
    parser.add_argument("--anthropic-max-requests", type=int, default=None)
    parser.add_argument(
        "--retry-openai-failures",
        action="store_true",
        help=(
            "Allow retrying OpenAI steps that previously failed "
            "with insufficient_quota"
        ),
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    state_dir = Path(args.state_dir)
    load_env_file(args.env_file)

    if (state_dir / "state.json").exists():
        state = load_state(state_dir)
    else:
        state = initialize_state(
            state_dir=state_dir,
            openai_model=args.openai_model,
            anthropic_model=args.anthropic_model,
            openai_runs=args.openai_runs,
            anthropic_runs=args.anthropic_runs,
            openai_run_start=args.openai_run_start,
            anthropic_run_start=args.anthropic_run_start,
        )
        save_state(state_dir, state)

    if args.command == "status":
        print(summarize_state(state))
        return 0

    poll_batches(state)
    materialized = materialize_completed_debates(state)
    save_state(state_dir, state)
    submitted = submit_ready_batches(
        state_dir=state_dir,
        state=state,
        openai_max_requests=args.openai_max_requests,
        anthropic_max_requests=args.anthropic_max_requests,
        retry_openai_failures=args.retry_openai_failures,
    )
    save_state(state_dir, state)

    print(summarize_state(state))
    if submitted:
        print(f"Submitted {submitted} new batch job(s).")
    if materialized:
        print(f"Wrote {materialized} completed debate file(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
