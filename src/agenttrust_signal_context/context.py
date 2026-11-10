"""Turn one Signal Feed issue into regime context and a guard decision.

An issue is a set of rule based market state labels. This module does
two things with it, both deterministic and offline:

1. summarize_issue reduces the issue to the label values an agent
   actually decides on, keeping the feed's own validity stamps and
   disclaimer attached.
2. evaluate_guard checks that context against a caller supplied
   policy (for example: only proceed when the BTC trend label is ON,
   stand aside when the VIX term structure reads STRESS) and returns
   a proceed or stand aside decision with a reason for every check.

The labels describe market state only. Nothing here predicts prices
or returns, and the summary always carries the feed's own disclaimer
so downstream code sees the context with its limits stated.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field


def canonical_issue_bytes(issue: dict) -> bytes:
    """Canonical form the seller hashes: JSON with sorted keys and
    compact separators, the integrity block excluded."""
    payload = {k: v for k, v in issue.items() if k != "integrity"}
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")


def verify_issue_integrity(issue: dict) -> bool | None:
    """Recompute the issue payload hash and compare it with the hash
    the issue carries. Returns None when the issue has no integrity
    block to check against."""
    integrity = issue.get("integrity") or {}
    expected = integrity.get("payload_sha256")
    if not expected:
        return None
    return hashlib.sha256(canonical_issue_bytes(issue)).hexdigest() == expected


@dataclass
class RegimeContext:
    feed: str | None = None
    disclaimer: str | None = None
    btc_trend_state: str | None = None  # "ON" or "OFF"
    btc_trend_valid_until: str | None = None
    alt_positive_count: int | None = None
    alt_universe_count: int | None = None
    alt_scores: dict = field(default_factory=dict)
    equity_spy_above_sma200: bool | None = None
    equity_vix_term_structure: str | None = None  # "CALM" or "STRESS"
    equity_valid_until: str | None = None
    mean_reversion_action: str | None = None
    mean_reversion_instrument: str | None = None
    mstr_btc_filter_state: str | None = None  # "ON" or "OFF"

    def to_dict(self) -> dict:
        return asdict(self)


def summarize_issue(issue: dict) -> RegimeContext:
    """Reduce a raw issue to its decision facing labels."""
    indicators = issue.get("indicators") or {}
    btc = indicators.get("btc_trend") or {}
    alt = indicators.get("alt_trend") or {}
    equity = indicators.get("us_equity_regime") or {}
    mean_rev = indicators.get("us_mean_reversion") or {}
    mstr = indicators.get("mstr_btc_filter") or {}
    return RegimeContext(
        feed=issue.get("feed"),
        disclaimer=issue.get("disclaimer"),
        btc_trend_state=btc.get("state"),
        btc_trend_valid_until=btc.get("valid_until_utc"),
        alt_positive_count=alt.get("positive_count"),
        alt_universe_count=alt.get("universe_count"),
        alt_scores=alt.get("scores") or {},
        equity_spy_above_sma200=equity.get("spy_above_sma200"),
        equity_vix_term_structure=equity.get("vix_term_structure"),
        equity_valid_until=equity.get("valid_until_utc"),
        mean_reversion_action=mean_rev.get("action"),
        mean_reversion_instrument=mean_rev.get("instrument"),
        mstr_btc_filter_state=mstr.get("state"),
    )


@dataclass
class GuardPolicy:
    """Caller supplied conditions for proceeding after the check."""

    require_btc_trend_on: bool = False
    block_on_vix_stress: bool = False
    require_equity_above_sma200: bool = False
    min_alt_positive: int | None = None


@dataclass
class GuardDecision:
    proceed: bool
    reasons: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def evaluate_guard(context: RegimeContext, policy: GuardPolicy) -> GuardDecision:
    """Evaluate the policy against the context.

    Every required check that fails, or whose label is missing, adds a
    reason and blocks the decision: the guard fails closed on absent
    data rather than treating it as a pass.
    """
    checks: list[tuple[bool, str]] = []  # (passed, reason)
    if policy.require_btc_trend_on:
        if context.btc_trend_state == "ON":
            checks.append((True, "btc_trend is ON, as required"))
        elif context.btc_trend_state is None:
            checks.append((False, "btc_trend label is missing; required check fails closed"))
        else:
            checks.append(
                (False, f"btc_trend is {context.btc_trend_state}, policy requires ON")
            )
    if policy.block_on_vix_stress:
        if context.equity_vix_term_structure == "STRESS":
            checks.append((False, "vix_term_structure is STRESS; policy stands aside"))
        elif context.equity_vix_term_structure is None:
            checks.append(
                (False, "vix_term_structure label is missing; required check fails closed")
            )
        else:
            checks.append(
                (True, f"vix_term_structure is {context.equity_vix_term_structure}, not STRESS")
            )
    if policy.require_equity_above_sma200:
        if context.equity_spy_above_sma200 is True:
            checks.append((True, "SPY is above its SMA200, as required"))
        elif context.equity_spy_above_sma200 is None:
            checks.append(
                (False, "spy_above_sma200 label is missing; required check fails closed")
            )
        else:
            checks.append((False, "SPY is not above its SMA200; policy requires it above"))
    if policy.min_alt_positive is not None:
        count = context.alt_positive_count
        if count is None:
            checks.append(
                (False, "alt_trend positive_count is missing; required check fails closed")
            )
        elif count >= policy.min_alt_positive:
            checks.append(
                (
                    True,
                    f"alt_trend breadth is {count} of {context.alt_universe_count}, "
                    f"at or above the required {policy.min_alt_positive}",
                )
            )
        else:
            checks.append(
                (
                    False,
                    f"alt_trend breadth is {count} of {context.alt_universe_count}, "
                    f"below the required {policy.min_alt_positive}",
                )
            )
    return GuardDecision(
        proceed=all(passed for passed, _ in checks),
        reasons=[reason for _, reason in checks],
    )
