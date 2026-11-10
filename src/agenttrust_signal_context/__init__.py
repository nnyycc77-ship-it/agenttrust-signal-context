"""Signal Feed regime context: a guarded pre-decision check for agents."""

from .client import (
    LatestIssue,
    SettlementProof,
    SignalFeedClient,
    fetch_latest_issue,
    read_offer,
)
from .context import (
    GuardDecision,
    GuardPolicy,
    RegimeContext,
    evaluate_guard,
    summarize_issue,
    verify_issue_integrity,
)
from .terms import (
    FEED_URL,
    PaymentTerms,
    TermsMismatch,
    parse_payment_required,
    verify_terms,
)

__all__ = [
    "FEED_URL",
    "GuardDecision",
    "GuardPolicy",
    "LatestIssue",
    "PaymentTerms",
    "RegimeContext",
    "SettlementProof",
    "SignalFeedClient",
    "TermsMismatch",
    "evaluate_guard",
    "fetch_latest_issue",
    "parse_payment_required",
    "read_offer",
    "summarize_issue",
    "verify_issue_integrity",
    "verify_terms",
]
__version__ = "0.1.0"
