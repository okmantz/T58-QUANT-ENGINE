"""Agent desk on top of T58 ai: nine roles, enforced separation, an append-only record. See ``roles`` for the rules."""
from app.ai.agent_desk.agents import Context, run_candidate
from app.ai.agent_desk.desk import DECISIONS, Agent, Artifact, Desk, SeparationError, default_roster
from app.ai.agent_desk.roles import MUST_DIFFER, ROLE_ORDER, ROLES

__all__ = ["Agent", "Artifact", "Context", "DECISIONS", "Desk", "MUST_DIFFER", "ROLES", "ROLE_ORDER", "SeparationError", "default_roster", "run_candidate"]
