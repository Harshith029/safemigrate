from typing import Optional
from pydantic import Field, BaseModel


class MigrationAction(BaseModel):
    command: str = Field(
        ...,
        description="The action type: 'plan', 'execute_sql', 'inspect_schema', 'inspect_data', 'create_savepoint', 'rollback_savepoint', 'validate_schema', 'finish'"
    )
    sql: Optional[str] = Field(
        default=None,
        description="SQL statement to execute (required for execute_sql)"
    )
    table: Optional[str] = Field(
        default=None,
        description="Table name for inspect_data"
    )
    savepoint_name: Optional[str] = Field(
        default=None,
        description="Name for create_savepoint or rollback_savepoint"
    )
    plan: Optional[str] = Field(
        default=None,
        description="Migration plan in natural language (required for plan command)"
    )


class SchemaInfo(BaseModel):
    tables: dict = Field(default_factory=dict)
    foreign_keys: list = Field(default_factory=list)
    indexes: list = Field(default_factory=list)


class RewardBreakdown(BaseModel):
    schema_match: float = Field(default=0.0)
    data_integrity: float = Field(default=0.0)
    efficiency_bonus: float = Field(default=0.0)
    error_penalty: float = Field(default=0.0)
    destructive_penalty: float = Field(default=0.0)
    safety_bonus: float = Field(default=0.0)
    planning_bonus: float = Field(default=0.0)
    unsafe_destructive_penalty: float = Field(default=0.0)


class MigrationObservation(BaseModel):
    message: str = Field(..., description="Human-readable result of the action")
    current_schema: SchemaInfo = Field(default_factory=SchemaInfo)
    target_schema_description: str = Field(default="")
    step_count: int = Field(default=0)
    max_steps: int = Field(default=30)
    remaining_steps: int = Field(default=30)
    progress: float = Field(default=0.0, description="Migration progress 0.0 to 1.0")
    done: bool = Field(default=False)
    reward: float = Field(default=0.0)
    reward_breakdown: Optional[RewardBreakdown] = Field(default=None)
    error: Optional[str] = Field(default=None)
    data_preview: Optional[dict] = Field(default=None)
    execution_log: list = Field(default_factory=list)
    savepoints: list = Field(default_factory=list)
    schema_diff: Optional[dict] = Field(default=None)
    terminated: bool = Field(default=False, description="True if episode was force-terminated due to safety violation")


class MigrationState(BaseModel):
    episode_id: str = Field(default="")
    step_count: int = Field(default=0)
    task_id: str = Field(default="")
    task_difficulty: str = Field(default="")
    current_score: float = Field(default=0.0)
    data_integrity_score: float = Field(default=0.0)
    schema_match_score: float = Field(default=0.0)
    steps_used: int = Field(default=0)
    max_steps: int = Field(default=30)
    savepoints_created: int = Field(default=0)
    rollbacks_performed: int = Field(default=0)
    destructive_ops: int = Field(default=0)
    unsafe_destructive_ops: int = Field(default=0)
    errors_encountered: int = Field(default=0)
    plan_submitted: bool = Field(default=False)
    data_loss_detected: bool = Field(default=False)