"""Research ledger: what was read, what was asked, what was covered, and which families are closed.

    evidence   A-D evidence grade for each of the 100 v13 families (a prior for where to look, never a result)
    ledger     sources / queries / coverage ledgers (append-only JSON Lines under data/research_ledger/)
    closure    the HARD close rule that sits on top of the graveyard's soft, capped penalty

Nothing in this package can lift a candidate over a gate. It only records, orders and (for a closed family) refuses to re-spend
search budget on a hypothesis the graveyard has already buried, until a person reopens it with a written reason.
"""
from app.research_ledger.closure import (  # noqa: F401
    ClosureDecision, ClosureRules, close_report, closed_families, evaluate_family, filter_open, is_closed, reopen_family,
)
from app.research_ledger.evidence import EVIDENCE, GRADE_TEXT, family_grade, grade_table, validate_coverage  # noqa: F401
from app.research_ledger.ledger import (  # noqa: F401
    ResearchLedger, coverage_summary, log_query, log_source, record_coverage, sync_coverage_from_graveyard,
)
