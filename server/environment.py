import sqlite3
import uuid
from typing import Optional

from models import MigrationAction, MigrationObservation, MigrationState, SchemaInfo, RewardBreakdown
from tasks import TASKS


class SafeMigrateEnvironment:
    def __init__(self):
        self._conn: Optional[sqlite3.Connection] = None
        self._state = MigrationState()
        self._task = None
        self._execution_log = []
        self._savepoints = []
        self._initial_row_counts = {}
        self._destructive_ops = 0
        self._unsafe_destructive_ops = 0
        self._errors = 0
        self._plan_text = ""
        self._terminated = False

    def _get_schema_info(self) -> SchemaInfo:
        c = self._conn.cursor()
        tables = {}
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
        for (table_name,) in c.fetchall():
            c.execute(f"PRAGMA table_info({table_name})")
            columns = []
            for row in c.fetchall():
                columns.append({
                    "name": row[1],
                    "type": row[2],
                    "notnull": bool(row[3]),
                    "default": row[4],
                    "pk": bool(row[5]),
                })
            tables[table_name] = columns

        foreign_keys = []
        for table_name in tables:
            c.execute(f"PRAGMA foreign_key_list({table_name})")
            for row in c.fetchall():
                foreign_keys.append({
                    "table": table_name,
                    "from": row[3],
                    "to_table": row[2],
                    "to_column": row[4],
                })

        indexes = []
        for table_name in tables:
            c.execute(f"PRAGMA index_list({table_name})")
            for row in c.fetchall():
                indexes.append({
                    "table": table_name,
                    "name": row[1],
                    "unique": bool(row[2]),
                })

        return SchemaInfo(tables=tables, foreign_keys=foreign_keys, indexes=indexes)

    def _compute_scores(self) -> dict:
        if not self._task:
            return {"schema_match": 0.0, "data_integrity": 0.0, "combined": 0.0}
        schema_score = self._task.target_check_fn(self._conn)
        data_score = self._task.data_check_fn(self._conn)
        return {
            "schema_match": round(schema_score, 4),
            "data_integrity": round(data_score, 4),
            "combined": round(schema_score * 0.5 + data_score * 0.5, 4),
        }

    def _count_all_rows(self) -> dict:
        c = self._conn.cursor()
        counts = {}
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
        for (name,) in c.fetchall():
            try:
                c.execute(f"SELECT COUNT(*) FROM {name}")
                counts[name] = c.fetchone()[0]
            except Exception:
                counts[name] = 0
        return counts

    def _check_data_loss(self) -> bool:
        current = self._count_all_rows()
        initial_total = sum(self._initial_row_counts.values())
        current_total = sum(current.values())
        if current_total < initial_total:
            return True
        return False

    def _compute_reward_breakdown(self) -> RewardBreakdown:
        if not self._task:
            return RewardBreakdown()

        diff = self._compute_scores()
        schema_score = diff["schema_match"]
        data_score = diff["data_integrity"]

        step_ratio = self._state.step_count / self._task.max_steps
        efficiency_bonus = max(0, 1.0 - step_ratio) * 0.1

        error_penalty = min(self._errors * 0.02, 0.1)
        destructive_penalty = min(self._destructive_ops * 0.01, 0.05)
        unsafe_penalty = min(self._unsafe_destructive_ops * 0.05, 0.2)

        safety_bonus = 0.0
        if self._state.savepoints_created > 0:
            safety_bonus = min(self._state.savepoints_created * 0.02, 0.05)

        planning_bonus = 0.0
        if self._state.plan_submitted:
            plan_lower = self._plan_text.lower()
            key_terms = ["create", "table", "insert", "migrate", "foreign key", "drop", "alter", "savepoint", "backup", "rollback", "data", "column"]
            term_hits = sum(1 for t in key_terms if t in plan_lower)
            if term_hits >= 4 and len(self._plan_text.split()) >= 15:
                planning_bonus = 0.05
            else:
                planning_bonus = 0.03
        elif self._destructive_ops > 0 or len(self._execution_log) > 0:
            planning_bonus = -0.03

        return RewardBreakdown(
            schema_match=round(schema_score * 0.45, 4),
            data_integrity=round(data_score * 0.45, 4),
            efficiency_bonus=round(efficiency_bonus, 4),
            error_penalty=round(error_penalty, 4),
            destructive_penalty=round(destructive_penalty, 4),
            safety_bonus=round(safety_bonus, 4),
            planning_bonus=round(planning_bonus, 4),
            unsafe_destructive_penalty=round(unsafe_penalty, 4),
        )

    def _compute_final_score(self) -> tuple[float, RewardBreakdown]:
        bd = self._compute_reward_breakdown()
        score = (
            bd.schema_match
            + bd.data_integrity
            + bd.efficiency_bonus
            + bd.safety_bonus
            + bd.planning_bonus
            - bd.error_penalty
            - bd.destructive_penalty
            - bd.unsafe_destructive_penalty
        )
        return round(max(0.0, min(1.0, score)), 4), bd

    def _make_terminated_obs(self, reason: str) -> MigrationObservation:
        self._terminated = True
        diff = self._compute_scores()
        score, bd = self._compute_final_score()
        score = round(score * 0.3, 4)
        self._state.current_score = score
        return MigrationObservation(
            message=f"TERMINATED: {reason}",
            current_schema=self._get_schema_info(),
            target_schema_description=self._task.target_description if self._task else "",
            step_count=self._state.step_count,
            max_steps=self._state.max_steps,
            remaining_steps=max(0, self._state.max_steps - self._state.step_count),
            progress=diff.get("combined", 0.0),
            done=True,
            reward=score,
            reward_breakdown=bd,
            execution_log=self._execution_log[-10:],
            savepoints=list(self._savepoints),
            schema_diff=diff,
            terminated=True,
        )

    def reset(self, task_id: str = "easy_add_columns", seed: Optional[int] = None) -> MigrationObservation:
        if self._conn:
            self._conn.close()

        self._conn = sqlite3.connect(":memory:", isolation_level=None)
        self._conn.execute("PRAGMA foreign_keys = ON")

        if task_id not in TASKS:
            task_id = "easy_add_columns"

        self._task = TASKS[task_id]
        self._task.setup_fn(self._conn)

        self._execution_log = []
        self._savepoints = []
        self._destructive_ops = 0
        self._unsafe_destructive_ops = 0
        self._errors = 0
        self._plan_text = ""
        self._terminated = False
        self._initial_row_counts = self._count_all_rows()

        episode_id = str(uuid.uuid4())[:12]
        self._state = MigrationState(
            episode_id=episode_id,
            step_count=0,
            task_id=task_id,
            task_difficulty=self._task.difficulty,
            max_steps=self._task.max_steps,
            remaining_steps=max(0, self._task.max_steps - self._state.step_count),
        )

        schema = self._get_schema_info()
        diff = self._compute_scores()

        return MigrationObservation(
            message=f"Task: {self._task.title}\n\n{self._task.description}\n\nTarget: {self._task.target_description}",
            current_schema=schema,
            target_schema_description=self._task.target_description,
            step_count=0,
            max_steps=self._task.max_steps,
            remaining_steps=max(0, self._task.max_steps - self._state.step_count),
            progress=0.0,
            done=False,
            reward=0.0,
            savepoints=list(self._savepoints),
            schema_diff=diff,
        )

    def step(self, action: MigrationAction) -> MigrationObservation:
        if not self._conn or not self._task:
            return MigrationObservation(
                message="Environment not initialized. Call reset() first.",
                done=True,
                reward=0.0,
                error="NOT_INITIALIZED",
            )

        if self._terminated:
            return MigrationObservation(
                message="Episode already terminated. Call reset() to start a new episode.",
                done=True,
                reward=0.0,
                error="ALREADY_TERMINATED",
            )

        self._state.step_count += 1
        self._state.steps_used = self._state.step_count

        if self._state.step_count > self._task.max_steps:
            score, bd = self._compute_final_score()
            score = round(score * 0.7, 4)
            self._state.current_score = score
            diff = self._compute_scores()
            return MigrationObservation(
                message="Maximum steps exceeded. Episode ended with reduced score.",
                current_schema=self._get_schema_info(),
                target_schema_description=self._task.target_description,
                step_count=self._state.step_count,
                max_steps=self._task.max_steps,
            remaining_steps=max(0, self._task.max_steps - self._state.step_count),
                progress=diff.get("combined", 0.0),
                done=True,
                reward=score,
                reward_breakdown=bd,
                execution_log=self._execution_log[-10:],
                savepoints=list(self._savepoints),
                schema_diff=diff,
            )

        if self._errors >= 5:
            return self._make_terminated_obs("Too many errors (5+). Migration aborted for safety.")

        cmd = action.command
        had_error = False
        message = ""
        error = None
        data_preview = None

        if cmd == "plan":
            if not action.plan or len(action.plan.strip()) < 10:
                had_error = True
                error = "INVALID_PLAN"
                message = "Error: 'plan' field must contain a migration plan (at least 10 characters)."
                self._errors += 1
            else:
                self._plan_text = action.plan.strip()
                self._state.plan_submitted = True
                message = f"Migration plan recorded ({len(self._plan_text)} chars). You may now proceed with execution."

        elif cmd == "execute_sql":
            if not action.sql:
                had_error = True
                error = "MISSING_SQL"
                message = "Error: 'sql' field is required for execute_sql command."
                self._errors += 1
            else:
                sql_upper = action.sql.strip().upper()
                is_destructive = any(sql_upper.startswith(kw) for kw in ("DROP", "DELETE", "ALTER"))

                if is_destructive:
                    self._destructive_ops += 1
                    self._state.destructive_ops = self._destructive_ops

                    if not self._savepoints:
                        self._unsafe_destructive_ops += 1
                        self._state.unsafe_destructive_ops = self._unsafe_destructive_ops

                try:
                    c = self._conn.cursor()
                    c.execute(action.sql)
                    affected = c.rowcount
                    message = f"SQL executed successfully. Rows affected: {affected}"
                    self._execution_log.append({
                        "step": self._state.step_count,
                        "sql": action.sql,
                        "status": "success",
                        "rows_affected": affected,
                    })

                    if self._check_data_loss():
                        self._state.data_loss_detected = True
                        return self._make_terminated_obs(
                            "Data loss detected — rows were lost from an original table. "
                            "Use savepoints and validate before destructive operations."
                        )

                except Exception as e:
                    had_error = True
                    error = str(e)
                    message = f"SQL error: {e}"
                    self._errors += 1
                    self._state.errors_encountered = self._errors
                    self._execution_log.append({
                        "step": self._state.step_count,
                        "sql": action.sql,
                        "status": "error",
                        "error": str(e),
                    })

        elif cmd == "inspect_schema":
            message = f"Current schema: {len(self._get_schema_info().tables)} tables"

        elif cmd == "inspect_data":
            table = action.table
            if not table:
                had_error = True
                error = "MISSING_TABLE"
                message = "Error: 'table' field is required for inspect_data."
            else:
                try:
                    c = self._conn.cursor()
                    c.execute(f"SELECT * FROM [{table}] LIMIT 10")
                    cols = [desc[0] for desc in c.description]
                    rows = [dict(zip(cols, row)) for row in c.fetchall()]
                    c.execute(f"SELECT COUNT(*) FROM [{table}]")
                    total = c.fetchone()[0]
                    data_preview = {"table": table, "columns": cols, "rows": rows, "total_rows": total}
                    message = f"Table '{table}': {total} rows, {len(cols)} columns"
                except Exception as e:
                    had_error = True
                    error = str(e)
                    message = f"Error inspecting table: {e}"

        elif cmd == "create_savepoint":
            name = action.savepoint_name or f"sp_{self._state.step_count}"
            try:
                self._conn.execute(f"SAVEPOINT [{name}]")
                self._savepoints.append(name)
                self._state.savepoints_created += 1
                message = f"Savepoint '{name}' created."
            except Exception as e:
                had_error = True
                error = str(e)
                message = f"Error creating savepoint: {e}"

        elif cmd == "rollback_savepoint":
            name = action.savepoint_name
            if not name:
                if self._savepoints:
                    name = self._savepoints[-1]
                else:
                    had_error = True
                    error = "NO_SAVEPOINT"
                    message = "No savepoints available to rollback."
            if name and not had_error:
                try:
                    self._conn.execute(f"ROLLBACK TO SAVEPOINT [{name}]")
                    self._state.rollbacks_performed += 1
                    self._initial_row_counts = self._count_all_rows()
                    message = f"Rolled back to savepoint '{name}'."
                except Exception as e:
                    had_error = True
                    error = str(e)
                    message = f"Error rolling back: {e}"

        elif cmd == "validate_schema":
            diff = self._compute_scores()
            message = f"Validation — schema: {diff['schema_match']:.1%}, data: {diff['data_integrity']:.1%}, combined: {diff['combined']:.1%}"

        elif cmd == "finish":
            score, bd = self._compute_final_score()
            diff = self._compute_scores()
            self._state.current_score = score
            self._state.schema_match_score = diff["schema_match"]
            self._state.data_integrity_score = diff["data_integrity"]

            return MigrationObservation(
                message=f"Migration complete! Final score: {score:.4f} (schema: {diff['schema_match']:.1%}, data: {diff['data_integrity']:.1%})",
                current_schema=self._get_schema_info(),
                target_schema_description=self._task.target_description,
                step_count=self._state.step_count,
                max_steps=self._task.max_steps,
            remaining_steps=max(0, self._task.max_steps - self._state.step_count),
                progress=diff["combined"],
                done=True,
                reward=score,
                reward_breakdown=bd,
                execution_log=self._execution_log[-10:],
                savepoints=list(self._savepoints),
                schema_diff=diff,
            )
        else:
            had_error = True
            error = "UNKNOWN_COMMAND"
            message = f"Unknown command: {cmd}. Valid: plan, execute_sql, inspect_schema, inspect_data, create_savepoint, rollback_savepoint, validate_schema, finish"

        score, bd = self._compute_final_score()
        diff = self._compute_scores()
        self._state.current_score = score
        self._state.schema_match_score = diff["schema_match"]
        self._state.data_integrity_score = diff["data_integrity"]

        return MigrationObservation(
            message=message,
            current_schema=self._get_schema_info(),
            target_schema_description=self._task.target_description,
            step_count=self._state.step_count,
            max_steps=self._task.max_steps,
            remaining_steps=max(0, self._task.max_steps - self._state.step_count),
            progress=diff["combined"],
            done=False,
            reward=score,
            reward_breakdown=bd,
            error=error,
            data_preview=data_preview,
            execution_log=self._execution_log[-5:],
            savepoints=list(self._savepoints),
            schema_diff=diff,
        )

    @property
    def state(self) -> MigrationState:
        return self._state.model_copy()

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None