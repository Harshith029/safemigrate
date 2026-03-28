"""
SafeMigrate Inference Script
===================================
MANDATORY
- Before submitting, ensure the following variables are defined in your environment configuration:
    API_BASE_URL   The API endpoint for the LLM.
    MODEL_NAME     The model identifier to use for inference.
    HF_TOKEN       Your Hugging Face / API key.

- The inference script must be named `inference.py` and placed in the root directory of the project
- Participants must use OpenAI Client for all LLM calls using above variables
"""

import os
import re
import json
import requests

from openai import OpenAI

API_BASE_URL = os.getenv("API_BASE_URL", "https://router.huggingface.co/v1")
API_KEY = os.getenv("HF_TOKEN") or os.getenv("API_KEY")
MODEL_NAME = os.getenv("MODEL_NAME", "meta-llama/Llama-3.1-8B-Instruct")
SPACE_URL = os.getenv("SAFEMIGRATE_URL", "https://Harshdev09-safemigrate.hf.space")

TASKS = ["easy_add_columns", "medium_normalize_tables", "hard_full_restructure"]

SYSTEM_PROMPT = """You are a database migration agent. Transform the current schema to match the target.

Commands (respond with JSON only, no explanation):
- {"command": "plan", "plan": "..."} — submit migration plan FIRST
- {"command": "execute_sql", "sql": "..."} — run SQL
- {"command": "inspect_schema"} — view schema
- {"command": "inspect_data", "table": "..."} — preview data
- {"command": "create_savepoint", "savepoint_name": "..."} — checkpoint BEFORE destructive ops
- {"command": "rollback_savepoint", "savepoint_name": "..."} — undo
- {"command": "validate_schema"} — check progress
- {"command": "finish"} — complete migration

Rules:
1. Submit a plan first
2. Create savepoints BEFORE any DROP/DELETE/ALTER
3. Validate before finishing
4. Respond ONLY with a single JSON object, no markdown, no explanation"""


def parse_action(content):
    content = content.strip()
    content = content.strip("`").strip()
    if content.startswith("json"):
        content = content[4:].strip()
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r'\{[^{}]*\}', content, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
    return {"command": "finish"}


def run_task(client, task_id):
    print(f"\n{'=' * 60}")
    print(f"Task: {task_id}")
    print(f"{'=' * 60}")

    obs = requests.post(f"{SPACE_URL}/reset", json={"task_id": task_id}, timeout=30).json()
    max_steps = obs["max_steps"]

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"{obs['message']}\n\nCurrent schema:\n{json.dumps(obs['current_schema'], indent=2)}"},
    ]

    for step in range(1, max_steps + 1):
        try:
            completion = client.chat.completions.create(
                model=MODEL_NAME,
                messages=messages,
                temperature=0.2,
                max_tokens=500,
                stream=False,
            )
            response_text = completion.choices[0].message.content or ""
        except Exception as e:
            print(f"  Step {step}: LLM error ({e}), finishing")
            response_text = '{"command": "finish"}'

        action = parse_action(response_text)
        obs = requests.post(f"{SPACE_URL}/step", json=action, timeout=30).json()

        cmd = action.get("command", "?")
        msg = obs.get("message", "")[:80]
        progress = obs.get("progress", 0)
        print(f"  Step {step}: {cmd} -> {msg} (progress: {progress:.1%})")

        messages.append({"role": "assistant", "content": json.dumps(action)})
        messages.append({"role": "user", "content": f"Result: {obs['message']}\nProgress: {progress:.1%}\nSchema diff: {json.dumps(obs.get('schema_diff', {}))}"})

        if obs.get("done"):
            break

    grade = requests.get(f"{SPACE_URL}/grader", timeout=30).json()
    print(f"\n  Final score: {grade['score']}")
    print(f"  Steps used: {grade['steps_used']}/{grade['max_steps']}")
    return grade


def run_scripted_baseline():
    print("\nRunning scripted baseline (no LLM)...\n")
    results = requests.get(f"{SPACE_URL}/baseline", timeout=120).json()
    for tid, g in results["baseline_scores"].items():
        print(f"  {tid}: score={g['score']}  steps={g['steps_used']}/{g['max_steps']}")
    return results


def main():
    print("SafeMigrate Inference Script")
    print(f"Space: {SPACE_URL}")
    print(f"API: {API_BASE_URL}")
    print(f"Model: {MODEL_NAME}")
    print(f"API Key: {'set' if API_KEY else 'NOT SET'}")

    if not API_KEY:
        print("\nNo HF_TOKEN or API_KEY set. Running scripted baseline...")
        run_scripted_baseline()
        return

    client = OpenAI(base_url=API_BASE_URL, api_key=API_KEY)

    scores = {}
    for task_id in TASKS:
        grade = run_task(client, task_id)
        scores[task_id] = grade

    print(f"\n{'=' * 60}")
    print("RESULTS")
    print(f"{'=' * 60}")
    for tid, g in scores.items():
        print(f"  {tid}: {g['score']}")

    print("\nAlso running scripted baseline for comparison...")
    run_scripted_baseline()


if __name__ == "__main__":
    main()