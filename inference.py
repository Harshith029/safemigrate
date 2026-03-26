import os
import json
import requests

BASE_URL = os.environ.get("SAFEMIGRATE_URL", "http://localhost:7860")
TASKS = ["easy_add_columns", "medium_normalize_tables", "hard_full_restructure"]


def run_scripted():
    results = requests.get(f"{BASE_URL}/baseline").json()
    return results


def main():
    print("SafeMigrate Baseline Inference")
    print(f"Server: {BASE_URL}")

    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        print("\nNo OPENAI_API_KEY set. Running scripted baseline...\n")
        results = run_scripted()
        for tid, g in results["baseline_scores"].items():
            print(f"  {tid}: score={g['score']} (steps={g['steps_used']}/{g['max_steps']})")
        print("\nDone.")
        return

    from openai import OpenAI
    client = OpenAI(api_key=api_key)

    system_prompt = """You are a database migration agent. Transform the current schema to match the target.

Commands (respond with JSON only):
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
4. Respond ONLY with a single JSON object"""

    scores = {}
    for task_id in TASKS:
        obs = requests.post(f"{BASE_URL}/reset", json={"task_id": task_id}).json()
        print(f"\n{'='*60}\nTask: {task_id}\n{'='*60}")

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"{obs['message']}\n\nSchema: {json.dumps(obs['current_schema'])}"},
        ]

        max_steps = obs["max_steps"]
        for step in range(max_steps):
            try:
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=messages,
                    temperature=0,
                    max_tokens=500,
                )
                content = response.choices[0].message.content.strip()
                content = content.strip("`").removeprefix("json").strip()
                action = json.loads(content)
            except Exception as e:
                print(f"  Step {step+1}: LLM error ({e}), finishing")
                action = {"command": "finish"}

            obs = requests.post(f"{BASE_URL}/step", json=action).json()
            print(f"  Step {step+1}: {action.get('command', '?')} -> {obs['message'][:80]}")

            messages.append({"role": "assistant", "content": json.dumps(action)})
            messages.append({"role": "user", "content": f"Result: {obs['message']}\nProgress: {obs.get('progress', 0):.1%}"})

            if obs.get("done"):
                break

        grade = requests.get(f"{BASE_URL}/grader").json()
        print(f"  Final score: {grade['score']}")
        scores[task_id] = grade

    print(f"\n{'='*60}\nRESULTS\n{'='*60}")
    for tid, g in scores.items():
        print(f"  {tid}: {g['score']}")


if __name__ == "__main__":
    main()