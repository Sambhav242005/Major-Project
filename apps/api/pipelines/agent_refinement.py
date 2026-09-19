"""Shim — preserves `from pipelines.agent_refinement import X` for backward compat."""
from pipelines.refinement import (
    MAX_SKILLS_PER_AGENT,
    MAX_SKILL_FAILURES,
    STAGNATION_ALARM_CYCLES,
    _evaluate_output_rule_based,
    evaluate_on_split,
    store_run_trace,
    mine_failures,
    propose_skill_delta,
    apply_delta,
    run_refinement_cycle,
)

__all__ = [
    "MAX_SKILLS_PER_AGENT",
    "MAX_SKILL_FAILURES",
    "STAGNATION_ALARM_CYCLES",
    "_evaluate_output_rule_based",
    "evaluate_on_split",
    "store_run_trace",
    "mine_failures",
    "propose_skill_delta",
    "apply_delta",
    "run_refinement_cycle",
]
