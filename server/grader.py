from server.environment import SafeMigrateEnvironment


def grade_episode(env: SafeMigrateEnvironment) -> dict:
    if not env._task or not env._conn:
        return {"score": 0.0, "breakdown": {}, "error": "No active episode"}

    score, bd = env._compute_final_score()

    return {
        "score": score,
        "breakdown": bd.model_dump(),
        "task_id": env._task.task_id,
        "difficulty": env._task.difficulty,
        "steps_used": env._state.step_count,
        "max_steps": env._task.max_steps,
        "plan_submitted": env._state.plan_submitted,
        "savepoints_used": env._state.savepoints_created,
        "errors": env._errors,
        "destructive_ops": env._destructive_ops,
        "unsafe_destructive_ops": env._unsafe_destructive_ops,
        "data_loss_detected": env._state.data_loss_detected,
    }