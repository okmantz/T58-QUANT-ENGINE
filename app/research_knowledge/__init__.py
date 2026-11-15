"""Research knowledge distilled from the Unified Study, Statistical_Methodology.md and Project_Specifications.md.

One place for the facts every engine (discovery, test, optimize, validate) and the AI assistant share: the 60-hypothesis registry,
the SF1-SF11 families, the decision gates, the zero-edge null and the Lucid rules with their evidence tiers.
"""
from .hypotheses import HYPOTHESES, Hypothesis, get as get_hypothesis, status_counts  # noqa: F401
from .methodology import FAMILIES, GATES, zero_edge_pass_probability, assistant_brief, engine_family_to_sf, rank_engine_families, sf_score  # noqa: F401
