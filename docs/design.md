# SafeMigrate — Design Document

## Problem statement

Database schema migrations are a universal pain point in software engineering. Every team with a relational database performs them. Every team has war stories about migrations gone wrong — production outages, corrupted data, three-hour rollbacks at 2 AM.

The core challenge is that migrations are multi-step, order-dependent, partially irreversible sequences of operations where a single mistake can cascade into data loss. This makes them an ideal candidate for training AI agents: the task is well-defined, the success criteria are objective, and the consequences of failure are clear.

Yet no standardized RL environment exists for database migration. SafeMigrate fills this gap.

## Why reinforcement learning fits

Traditional approaches to automated migration (code generation, template-based tools) produce a migration script and hope it works. They do not learn from execution feedback, cannot recover from errors mid-migration, and have no concept of safety constraints.

RL is fundamentally different. An RL agent interacts with the environment step-by-step, observes the consequences of each action, and adapts its strategy based on reward signals. This maps naturally to how experienced engineers perform migrations: inspect the current state, plan the approach, create a safety checkpoint, execute a step, verify the result, and continue or rollback based on what happened.

The key insight is that migration is not a single-shot generation problem — it is a sequential decision problem under uncertainty. The agent must decide at each step whether to execute SQL, inspect data, create a savepoint, validate progress, or finish. These decisions depend on the current state of the database, the history of actions taken, and the remaining step budget.

## Environment design decisions

### Action space design

The action space was designed to mirror the tools available to a real engineer performing a migration:

- **plan** — engineers always plan before executing. The plan action encourages agents to reason about their approach before touching data. A planning bonus rewards this behavior.
- **execute_sql** — the core action. Accepts arbitrary SQL, returning success/failure feedback. This gives agents maximum flexibility while making them responsible for correctness.
- **inspect_schema / inspect_data** — information gathering. Agents must understand the current state before making changes. Schema introspection returns table structures, column types, foreign keys, and indexes.
- **create_savepoint / rollback_savepoint** — safety mechanisms. These map directly to SQL savepoints. The environment penalizes destructive operations performed without a prior savepoint, teaching agents defensive engineering practices.
- **validate_schema** — progress checking. Returns real-time schema match and data integrity scores so agents can verify their work before declaring completion.
- **finish** — explicit completion signal with final scoring.

### Observation space design

Every observation includes the full current schema, progress score, reward breakdown, and execution history. This follows the principle of maximum transparency — the agent should never need to guess about the environment state. The reward breakdown is included so agents and researchers can understand exactly which signals are driving learning.

### Reward function design

The reward function was designed with three principles:

1. **Alignment** — the same computation is used for step rewards, final scores, and the grader endpoint. There is no discrepancy between what the agent optimizes and what the judge evaluates.

2. **Multi-signal** — binary success/failure is a weak training signal. Instead, the reward decomposes into schema match (45%), data integrity (45%), efficiency bonus, planning bonus, safety bonus, and penalties. This provides gradient throughout the episode.

3. **Safety incentives** — destructive operations are penalized. Destructive operations without savepoints are heavily penalized. Data loss terminates the episode. This teaches agents that safety is not optional.

### Task design

Three tasks provide a clear difficulty progression:

- **Easy** — additive schema change (no data movement, no table recreation). Tests basic SQL competence.
- **Medium** — normalization requiring data extraction into new tables, foreign key creation, and source table reconstruction. Tests multi-step planning and data preservation.
- **Hard** — full restructure with real-world data quality issues (NULL values, case-inconsistent naming, missing fields). Tests robustness to messy data and edge case handling.

The hard task is specifically designed to challenge frontier models. A model that can generate perfect SQL for clean data may still fail when encountering "techcorp" vs "TechCorp" or NULL supplier fields. This reflects production reality — the data is never as clean as the schema suggests.

### Safety termination

Episodes terminate under two conditions:

1. **Excessive errors (5+)** — an agent making repeated errors is not learning from feedback. Termination prevents infinite error loops and signals that the approach needs fundamental change.

2. **Data loss** — if any original table loses rows during migration, the episode terminates immediately. This is the strongest safety signal: in production, data loss is the worst possible outcome.

Terminated episodes receive only 30% of their current score, creating a strong incentive to avoid these conditions.

## Technical implementation

### SQLite as the execution engine

SQLite was chosen deliberately:

- Zero external dependencies (included in Python standard library)
- In-memory databases provide perfect isolation between episodes
- SAVEPOINT support enables the rollback mechanism
- Foreign key enforcement via PRAGMA tests referential integrity
- Deterministic behavior ensures reproducible grading

### Grader determinism

Every grader check is a SQL query against the migrated database. Checks include:

- Table existence
- Column presence and types
- Foreign key relationships (via PRAGMA foreign_key_list)
- Row counts
- Specific data mapping verification (e.g., "does Gaming Laptop map to TechCorp?")
- Duplicate detection
- NULL handling validation
- Constraint enforcement

All checks produce scores between 0.0 and 1.0. The grader is fully deterministic — same database state always produces the same score.

### Containerization

The environment runs as a single FastAPI server in a Docker container. Port 7860 is used for Hugging Face Spaces compatibility. The health check endpoint ensures automated validation can confirm the Space is responsive. The single-worker configuration prevents concurrent session conflicts during evaluation.

## Future directions

- WebSocket support for persistent sessions (aligned with OpenEnv spec evolution)
- Additional tasks: index optimization, query performance tuning, cross-database migration
- Adversarial data generation for even harder dirty data scenarios
- Multi-agent cooperative migration (DBA + developer roles)