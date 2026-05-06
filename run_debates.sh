#!/usr/bin/env bash

set -euo pipefail

OUTPUT_DIR="${1:-islam_debate/data/ollama_20260430}"
ROUNDS="${ROUNDS:-1}"
LOG_LEVEL="${LOG_LEVEL:-INFO}"
RETURN_HTML="${RETURN_HTML:-false}"
RUN_START="${RUN_START:-1}"
RUN_END="${RUN_END:-1}"

models=(
  "llama3.1:8b"
  "gemma3:12b"
  "qwen3:14b"
  "mistral-small3.1:24b"
  "deepseek-r1:14b"
  "gemma3:27b"
)

topics=(
  "Islam encourages violence towards women"
  "Islam permits Muslims to eat any beef sold in Christian countries"
  "Islam permits Muslims to take mortgages with interest"
  "Islam permits homosexuality"
  "Islam permits music"
  "Islam promotes peace"
  "Islam promotes violence towards non Muslims"
  "Islam promotes women's rights"
  "Muslims can be active citizens in secular countries"
  "Muslims cannot live in secular countries"
)

slugify() {
  printf '%s' "$1" \
    | tr '[:upper:]' '[:lower:]' \
    | sed -E "s/'//g; s/[^a-z0-9]+/_/g; s/^_+//; s/_+$//"
}

mkdir -p "$OUTPUT_DIR"

for ((run_number = RUN_START; run_number <= RUN_END; run_number++)); do
  run_label="$(printf 'run%02d' "$run_number")"
  for model in "${models[@]}"; do
    model_slug="$(slugify "$model")"
    for topic in "${topics[@]}"; do
      topic_slug="$(slugify "$topic")"
      output_base="${OUTPUT_DIR}/${topic_slug}__${model_slug}"

      if [[ "$RUN_START" != "1" || "$RUN_END" != "1" ]]; then
        output_base="${output_base}__${run_label}"
      fi

      if [[ -f "${output_base}.json" ]]; then
        echo "Skipping existing result: ${output_base}.json"
        continue
      fi

      echo "Running ${run_label}: topic '${topic}' with model '${model}'"
      cmd=(
        uv run python -m islam_debate.main
        ollama
        "$model"
        "$topic"
        --rounds
        "$ROUNDS"
        --log-level
        "$LOG_LEVEL"
        --filename
        "$output_base"
      )

      if [[ "$RUN_START" != "1" || "$RUN_END" != "1" ]]; then
        cmd+=(--run-label "$run_label")
      fi

      if [[ "$RETURN_HTML" == "true" ]]; then
        cmd+=(--return-html)
      fi

      "${cmd[@]}"
    done
  done
done
