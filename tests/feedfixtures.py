"""Shared offline fixtures: a 402 offer and an issue in the live shapes.

The offer mirrors the fields the endpoint actually returns (amounts
and addresses are the published ones). The issue mirrors the schema
of the seller's published output example, with the integrity hash
computed the way the seller describes, so the hash check can be
exercised end to end offline.
"""

import base64
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from agenttrust_signal_context.context import canonical_issue_bytes  # noqa: E402
from agenttrust_signal_context.terms import (  # noqa: E402
    EXPECTED_AMOUNT_ATOMIC,
    EXPECTED_ASSET,
    EXPECTED_NETWORK,
    EXPECTED_PAY_TO,
    EXPECTED_SCHEME,
)


def offer_terms(**overrides):
    terms = {
        "scheme": EXPECTED_SCHEME,
        "network": EXPECTED_NETWORK,
        "asset": EXPECTED_ASSET,
        "amount": EXPECTED_AMOUNT_ATOMIC,
        "payTo": EXPECTED_PAY_TO,
        "maxTimeoutSeconds": 60,
        "extra": {"name": "USD Coin", "version": "2"},
    }
    terms.update(overrides)
    return terms


def offer_header(**overrides):
    payload = {"x402Version": 2, "accepts": [offer_terms(**overrides)]}
    return base64.b64encode(json.dumps(payload).encode("utf-8")).decode("ascii")


def sample_issue():
    issue = {
        "feed": "regime-feed",
        "disclaimer": (
            "Regime indicators derived from virtual (PAPER) research accounts "
            "with no real orders. Track record is short and unproven. "
            "Not investment advice."
        ),
        "indicators": {
            "btc_trend": {
                "state": "ON",
                "rule": "ON when BTC daily close > SMA50 AND SMA20 > SMA50.",
                "valid_until_utc": "2026-11-07T12:00:00Z",
            },
            "alt_trend": {
                "positive_count": 6,
                "universe_count": 9,
                "scores": {"ADA": 0.75, "ETH": 1.0, "SOL": 0.5},
                "valid_until_utc": "2026-11-07T12:00:00Z",
            },
            "us_equity_regime": {
                "spy_above_sma200": True,
                "vix_term_structure": "CALM",
                "valid_until_utc": "2026-11-07T12:00:00Z",
            },
            "us_mean_reversion": {"action": "STAY_FLAT", "instrument": "SPY"},
            "mstr_btc_filter": {"state": "OFF"},
        },
    }
    issue["integrity"] = {
        "canonicalization": (
            "JSON, keys sorted, separators (',', ':'), ASCII; "
            "integrity block excluded"
        ),
        "payload_sha256": hashlib.sha256(canonical_issue_bytes(issue)).hexdigest(),
    }
    return issue
