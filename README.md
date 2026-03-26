# SafeMigrate — Safety-Critical Database Migration Environment

> **SafeMigrate is the first OpenEnv benchmark for safety-critical infrastructure transformations.** Naive solutions fail due to hidden data inconsistencies, ordering dependencies, and irreversible consequences.

An OpenEnv-compatible reinforcement learning environment that simulates real-world database schema migrations. AI agents must plan, execute, and verify multi-step SQL migrations while preserving data integrity, managing rollbacks, and minimizing destructive operations — mirroring how real production engineering systems operate.

## Why this matters

Database migrations are one of the most high-stakes operations in software engineering. A single botched migration can cause production outages lasting hours, irreversible data loss affecting millions of users, and recovery costs reaching six figures. Yet despite this criticality, engineers still perform migrations semi-manually with fragile scripts and hope-based rollback strategies.

Training AI agents to safely execute migrations addresses a genuine gap in the RL ecosystem. No standardized environment exists for this task — not in OpenEnv, not in Gymnasium, not anywhere. SafeMigrate fills that gap with a fully deterministic, sandboxed environment that captures the core challenges of production migration work.

Real-world relevance for teams at Meta, Hugging Face, and every engineering organization: schema migrations happen daily across thousands of services. An agent that can plan, checkpoint, execute, and recover is not a toy — it is infrastructure.

## Why this is hard for AI

Database migrations require capabilities that most LLM agents struggle with:

**Planning under constraints.** The agent cannot simply generate SQL — it must reason about dependency ordering. Dropping a table referenced by foreign keys fails. Creating a table before its dependencies exist fails. The agent must construct a valid execution plan before touching any data.

**Safety-critical decision making.** Every destructive operation (DROP, DELETE, ALTER) is potentially irreversible. The environment penalizes agents that execute destructive operations without first creating savepoints. This forces the agent to learn defensive engineering practices rather than trial-and-error.

**Dirty data handling.** Real databases have inconsistencies. The hard task includes NULL suppliers, case-mismatched names ("techcorp" vs "TechCorp"), and missing subcategories. The agent must detect and handle these rather than assuming clean input.

**Multi-objective optimization.** The agent must simultaneously maximize schema correctness, preserve data integrity, minimize steps, avoid errors, and use safety mechanisms. These objectives sometimes conflict — speed vs safety, simplicity vs completeness.

**Failure recovery.** If the agent causes data loss, the episode terminates immediately. If errors accumulate beyond 5, the episode terminates. The agent must learn to recover from mistakes using rollbacks rather than pushing forward blindly.

## Action space

| Command | Fields | Description |
|---|---|---|
| `plan` | `plan` (required) | Submit a migration plan before executing. Earns a planning bonus. |
| `execute_sql` | `sql` (required) | Execute any SQL statement against the database |
| `inspect_schema` | — | View current schema (tables, columns, types, keys) |
| `inspect_data` | `table` (required) | Preview up to 10 rows from a table |
| `create_savepoint` | `savepoint_name` | Create a rollback checkpoint. Required before destructive ops. |
| `rollback_savepoint` | `savepoint_name` | Roll back to a previous checkpoint |
| `validate_schema` | — | Check current migration progress (schema + data scores) |
| `finish` | — | Declare migration complete and receive final score |

## Observation space

Each step returns:

- `message` — human-readable result
- `current_schema` — full schema snapshot (tables, columns, types, foreign keys, indexes)
- `target_schema_description` — natural language target description
- `progress` — migration progress from 0.0 to 1.0
- `schema_diff` — real-time scores: schema_match, data_integrity, combined
- `reward` — current reward signal
- `reward_breakdown` — transparent decomposition: schema_match, data_integrity, efficiency_bonus, error_penalty, destructive_penalty, safety_bonus, planning_bonus, unsafe_destructive_penalty
- `execution_log` — recent SQL executions with status
- `savepoints` — active savepoints
- `data_preview` — table data when using inspect_data
- `error` — error details if action failed
- `terminated` — whether episode was force-terminated for safety violation
- `step_count` / `max_steps` — remaining budget
- `done` — whether episode has ended

## Tasks

### Task 1: Add columns (easy) — max 15 steps

Add `email`, `hire_date`, and `is_active` columns to an employees table. The `is_active` column must be INTEGER type with DEFAULT 1. All 8 existing rows must be preserved with original values intact.

**Baseline score: 0.960**

### Task 2: Normalize schema (medium) — max 25 steps

Split a denormalized database into properly normalized tables: extract addresses from users (with FK), split orders into orders + order_items (with FK). Remove denormalized columns from source tables. Maintain all foreign key relationships and preserve all 4 users, 4 addresses, and 7 order items.

**Baseline score: 0.681**

### Task 3: Full restructure with dirty data (hard) — max 40 steps

Major multi-table restructure with real-world data quality challenges:
- Extract deduplicated suppliers — handle case mismatch ("techcorp" vs "TechCorp") and NULL suppliers
- Extract categories — handle NULL subcategories
- Create inventory tracking table
- Add proper foreign keys, drop all denormalized columns
- Preserve all 10 products and 10 sales with correct relationships

**Baseline score: 0.580**

The hard task specifically tests whether agents can handle data quality issues that are common in production but absent from toy environments.

## Reward function

The reward is a unified multi-signal score used consistently across step rewards, final scores, and the grader:

| Signal | Weight | Description |
|---|---|---|
| Schema match | 45% | How closely current schema matches target |
| Data integrity | 45% | Whether all original data is preserved correctly |
| Efficiency bonus | up to 10% | Bonus for completing in fewer steps |
| Planning bonus | 3% | Bonus for submitting a migration plan |
| Safety bonus | up to 5% | Bonus for creating savepoints |
| Error penalty | -2% each, max -10% | Penalty for SQL errors |
| Destructive penalty | -1% each, max -5% | Penalty for DROP/DELETE/ALTER operations |
| Unsafe destructive penalty | -5% each | Heavy penalty for destructive ops without prior savepoint |

**Safety termination conditions:**
- 5+ errors → episode terminated, score reduced to 30% of current
- Data loss detected → episode terminated immediately

## Setup

### Local development

```bash
pip install fastapi uvicorn pydantic
cd safemigrate
uvicorn server.app:app --host 0.0.0.0 --port 8000
```

### Docker

```bash
docker build -t safemigrate .
docker run -p 7860:7860 safemigrate
```

### Hugging Face Spaces

Deployed as a Docker Space at port 7860. Fully compatible with OpenEnv spec.

## Usage

```python
import requests

BASE = "http://localhost:7860"

tasks = requests.get(f"{BASE}/tasks").json()

obs = requests.post(f"{BASE}/reset", json={"task_id": "easy_add_columns"}).json()

obs = requests.post(f"{BASE}/step", json={
    "command": "plan",
    "plan": "Add email, hire_date, is_active columns using ALTER TABLE"
}).json()

obs = requests.post(f"{BASE}/step", json={
    "command": "create_savepoint",
    "savepoint_name": "before_changes"
}).json()

obs = requests.post(f"{BASE}/step", json={
    "command": "execute_sql",
    "sql": "ALTER TABLE employees ADD COLUMN email TEXT"
}).json()
print(obs["progress"], obs["reward_breakdown"])

obs = requests.post(f"{BASE}/step", json={"command": "validate_schema"}).json()

obs = requests.post(f"{BASE}/step", json={"command": "finish"}).json()
print(f"Score: {obs['reward']}")

grade = requests.get(f"{BASE}/grader").json()

baseline = requests.get(f"{BASE}/baseline").json()
```

## API endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/health` | GET | Health check |
| `/reset` | POST | Start new episode (task_id, optional seed) |
| `/step` | POST | Execute an action |
| `/state` | GET | Get current episode state |
| `/tasks` | GET | List all tasks with action schemas |
| `/grader` | GET | Get grader score for current episode |
| `/baseline` | GET | Run baseline inference on all tasks |

## Baseline scores

| Task | Difficulty | Score | Steps |
|---|---|---|---|
| easy_add_columns | Easy | 0.960 | 9 / 15 |
| medium_normalize_tables | Medium | 0.681 | 23 / 25 |
| hard_full_restructure | Hard | 0.580 | 17 / 40 |

Scores are fully reproducible. The scripted baseline intentionally does not solve all edge cases — it fails on foreign key constraints when dropping tables that are still referenced. A frontier LLM agent that discovers the `PRAGMA foreign_keys = OFF` workaround or restructures the migration order can significantly outperform these baselines.

## Architecture

- **SQLite in-memory** — each episode gets a fresh isolated database. Zero external dependencies.
- **Pydantic models** — fully typed Action, Observation, and State classes.
- **Unified scoring** — step rewards, final scores, and grader use the same computation.
- **Safety-first design** — termination on data loss, penalty for unprotected destructive ops.
- **FastAPI server** — async-ready HTTP API.
- **Docker-first** — single Dockerfile, HF Spaces compatible (port 7860).

## License

MIT