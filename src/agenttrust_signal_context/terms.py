"""Pinned payment terms for the Signal Feed API latest issue endpoint.

The endpoint sells one daily market regime issue through the x402
protocol. Before any authorization is signed, the live 402 offer is
read and every field is checked against the values the seller
publishes in its machine readable offers file
(https://signals.agenttrustapi.com/offers.json, terms version
2026-10-27). The offers file itself states that the live 402 response
is authoritative, so the check runs against the live offer on every
call, with the published values as the expectation.

This module is standard library only, so the term checks can be unit
tested offline and reused without the payment stack installed.
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass

FEED_URL = "https://signals.agenttrustapi.com/v1/feed/latest"
EXPECTED_SCHEME = "exact"
EXPECTED_NETWORK = "eip155:8453"  # Base mainnet
EXPECTED_ASSET = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"  # USDC on Base
EXPECTED_AMOUNT_ATOMIC = "40000"  # 0.04 USDC (seller cut the price from
# 0.10 on 2026-11-09; offers.json and the live 402 agree on 40000)
EXPECTED_PRICE_USDC = 0.04
EXPECTED_PAY_TO = "0x8b0ad0CE12Ac86822c4d5dE442F5e445d14F9183"


class TermsMismatch(ValueError):
    """The live 402 offer differs from the published terms."""


@dataclass(frozen=True)
class PaymentTerms:
    """One accept entry from an x402 402 response."""

    scheme: str
    network: str
    asset: str
    amount_atomic: str
    pay_to: str
    max_timeout_seconds: int | None = None
    asset_name: str | None = None
    asset_version: str | None = None


def parse_payment_required(header_value: str | None) -> PaymentTerms:
    """Decode a Payment-Required header (base64 JSON, x402 v2).

    Returns the first accept entry. Raises TermsMismatch when the
    header is missing or malformed.
    """
    if not header_value:
        raise TermsMismatch("402 response carried no Payment-Required header")
    try:
        decoded = json.loads(base64.b64decode(header_value).decode("utf-8"))
    except Exception as exc:  # malformed header: fail closed
        raise TermsMismatch(f"Payment-Required header is not decodable: {exc}") from exc
    accepts = decoded.get("accepts") or []
    if not accepts:
        raise TermsMismatch("402 response carried no accepts entries")
    first = accepts[0]
    extra = first.get("extra") or {}
    return PaymentTerms(
        scheme=str(first.get("scheme", "")),
        network=str(first.get("network", "")),
        asset=str(first.get("asset", "")),
        amount_atomic=str(first.get("amount", "")),
        pay_to=str(first.get("payTo", "")),
        max_timeout_seconds=first.get("maxTimeoutSeconds"),
        asset_name=extra.get("name"),
        asset_version=extra.get("version"),
    )


def verify_terms(terms: PaymentTerms, expected_pay_to: str = EXPECTED_PAY_TO) -> None:
    """Raise TermsMismatch unless every field matches the expectation.

    Addresses compare case insensitively; everything else must match
    exactly. Nothing is signed for an offer that fails this check.
    """
    problems = []
    if terms.scheme != EXPECTED_SCHEME:
        problems.append(f"scheme is {terms.scheme!r}, expected {EXPECTED_SCHEME!r}")
    if terms.network != EXPECTED_NETWORK:
        problems.append(f"network is {terms.network!r}, expected {EXPECTED_NETWORK!r}")
    if terms.asset.lower() != EXPECTED_ASSET.lower():
        problems.append(f"asset is {terms.asset!r}, expected {EXPECTED_ASSET!r}")
    if terms.amount_atomic != EXPECTED_AMOUNT_ATOMIC:
        problems.append(
            f"amount is {terms.amount_atomic!r}, expected {EXPECTED_AMOUNT_ATOMIC!r}"
        )
    if terms.pay_to.lower() != expected_pay_to.lower():
        problems.append(f"payTo is {terms.pay_to!r}, expected {expected_pay_to!r}")
    if problems:
        raise TermsMismatch("402 offer does not match the published terms: " + "; ".join(problems))
