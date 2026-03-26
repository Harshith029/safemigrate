import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

from models import MigrationAction
from server.environment import SafeMigrateEnvironment
from tasks import TASKS
from server.grader import grade_episode
from server.baseline import run_baseline


app = FastAPI(
    title="SafeMigrate",
    description="Safety-critical database migration environment for AI agents",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

sessions: dict[str, SafeMigrateEnvironment] = {}


def get_or_create_env(session_id: str = "default") -> SafeMigrateEnvironment:
    if session_id not in sessions:
        sessions[session_id] = SafeMigrateEnvironment()
    return sessions[session_id]


class ResetRequest(BaseModel):
    task_id: str = "easy_add_columns"
    seed: Optional[int] = None
    session_id: str = "default"


class StepRequest(BaseModel):
    command: str
    sql: Optional[str] = None
    table: Optional[str] = None
    savepoint_name: Optional[str] = None
    plan: Optional[str] = None
    session_id: str = "default"


@app.get("/health")
def health():
    return {"status": "ok", "environment": "safemigrate", "version": "1.0.0"}

@app.get("/")
def root():
    return {
        "name": "safemigrate",
        "description": "Safety-critical database migration environment for AI agents",
        "version": "1.0.0",
        "endpoints": ["/health", "/reset", "/step", "/state", "/tasks", "/grader", "/baseline"],
    }
    
@app.post("/reset")
def reset(req: ResetRequest):
    env = get_or_create_env(req.session_id)
    obs = env.reset(task_id=req.task_id, seed=req.seed)
    return obs.model_dump()


@app.post("/step")
def step(req: StepRequest):
    env = get_or_create_env(req.session_id)
    action = MigrationAction(
        command=req.command,
        sql=req.sql,
        table=req.table,
        savepoint_name=req.savepoint_name,
        plan=req.plan,
    )
    obs = env.step(action)
    return obs.model_dump()


@app.get("/state")
def state(session_id: str = "default"):
    env = get_or_create_env(session_id)
    return env.state.model_dump()


@app.get("/tasks")
def list_tasks():
    result = []
    for tid, task in TASKS.items():
        result.append({
            "task_id": tid,
            "difficulty": task.difficulty,
            "title": task.title,
            "description": task.description,
            "target_description": task.target_description,
            "max_steps": task.max_steps,
            "action_schema": {
                "command": {
                    "type": "string",
                    "enum": ["plan", "execute_sql", "inspect_schema", "inspect_data", "create_savepoint", "rollback_savepoint", "validate_schema", "finish"],
                },
                "sql": {"type": "string", "description": "SQL statement (for execute_sql)", "required": False},
                "table": {"type": "string", "description": "Table name (for inspect_data)", "required": False},
                "savepoint_name": {"type": "string", "description": "Savepoint name", "required": False},
                "plan": {"type": "string", "description": "Migration plan text (for plan command)", "required": False},
            },
        })
    return {"tasks": result}


@app.get("/grader")
def grader(session_id: str = "default"):
    env = get_or_create_env(session_id)
    return grade_episode(env)


@app.get("/baseline")
def baseline():
    return run_baseline()