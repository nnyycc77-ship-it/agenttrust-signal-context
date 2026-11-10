"""Guarded x402 client for the Signal Feed API latest issue.

The flow on every fetch is deliberately narrow:

1. Read the live 402 offer with a plain request. Nothing is signed.
2. Check the offer field by field against the terms the seller
   publishes (terms.py). Any difference stops the call before a
   signature exists.
3. Make exactly one attempt through the official x402 Python SDK,
   with the client spend control set to the published per call price.
   A failed or non 200 answer is raised to the caller and is never
   retried by this code.
4. Decode the PAYMENT-RESPONSE header into a settlement record and
   recompute the issue payload hash against the hash the issue
   carries, so the caller gets the data with its proof attached.

A per process budget (default two settlements, the seller's suggested
daily ceiling of 0.20 USDC) is counted before each attempt, so a loop
in calling code cannot turn into open ended spend.

Use a dedicated wallet holding a small USDC balance on Base. Never a
main wallet. The key is read from the caller's environment, used to
sign locally, and never logged or returned.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Callable, Optional

import requests

from .context import verify_issue_integrity
from .terms import (
    EXPECTED_PAY_TO,
    EXPECTED_PRICE_USDC,
    FEED_URL,
    PaymentTerms,
    parse_payment_required,
    verify_terms,
)

DEFAULT_TIMEOUT_S = 280  # the settled request waits on settlement; allow it real time
DEFAULT_MAX_SETTLEMENTS = 2
PAY_TO_ENV = "SIGNAL_FEED_EXPECTED_PAY_TO"


class FeedError(RuntimeError):
    """The fetch stopped before or during the single attempt."""


class SessionBudgetExceeded(FeedError):
    """The per process settlement budget is already spent."""


@dataclass
class SettlementProof:
    success: bool
    payer: str
    network: str
    transaction: str
    amount_atomic: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "payer": self.payer,
            "network": self.network,
            "transaction": self.transaction,
            "amount_atomic": self.amount_atomic,
        }


@dataclass
class LatestIssue:
    issue: dict
    terms: PaymentTerms
    settlement: Optional[SettlementProof]
    integrity_ok: Optional[bool]


def read_offer(session, url: str = FEED_URL, timeout: int = 30) -> PaymentTerms:
    """Fetch the live 402 offer without signing anything."""
    response = session.get(url, timeout=timeout)
    if response.status_code != 402:
        raise FeedError(
            f"expected HTTP 402 from {url}, got {response.status_code}; nothing signed"
        )
    return parse_payment_required(response.headers.get("Payment-Required"))


def decode_settlement(raw_header: Optional[str]) -> Optional[SettlementProof]:
    """Decode a PAYMENT-RESPONSE header into a settlement record."""
    if not raw_header:
        return None
    from x402.http.utils import decode_payment_response_header

    settlement = decode_payment_response_header(raw_header)
    if settlement is None:
        return None
    return SettlementProof(
        success=bool(settlement.success),
        payer=str(settlement.payer),
        network=str(settlement.network),
        transaction=str(settlement.transaction),
        amount_atomic=str(settlement.amount) if settlement.amount is not None else None,
    )


class SignalFeedClient:
    """One guarded fetch of the latest issue per call."""

    def __init__(
        self,
        private_key: str,
        expected_pay_to: Optional[str] = None,
        max_settlements: int = DEFAULT_MAX_SETTLEMENTS,
        timeout: int = DEFAULT_TIMEOUT_S,
        session_factory: Callable = requests.Session,
        payment_session_factory: Optional[Callable] = None,
        settlement_decoder: Callable = decode_settlement,
    ):
        if not private_key:
            raise ValueError("a wallet key is required to fetch the latest issue")
        self._private_key = private_key
        self.expected_pay_to = (
            expected_pay_to
            or os.environ.get(PAY_TO_ENV)
            or EXPECTED_PAY_TO
        )
        self.max_settlements = max_settlements
        self.timeout = timeout
        self._session_factory = session_factory
        self._payment_session_factory = payment_session_factory or self._build_payment_session
        self._decode = settlement_decoder
        self._settlements_attempted = 0

    def _build_payment_session(self):
        """An x402 aware requests session, capped at the per call price."""
        from eth_account import Account
        from x402 import x402ClientSync
        from x402.http.clients.requests import wrapRequestsWithPayment
        from x402.mechanisms.evm.exact.client import ExactEvmScheme
        from x402.mechanisms.evm.signers import EthAccountSigner

        account = Account.from_key(self._private_key)
        client = x402ClientSync()
        client.register("eip155:*", ExactEvmScheme(EthAccountSigner(account)))
        client.set_spend_controls({"max_amount_per_payment": EXPECTED_PRICE_USDC})
        return wrapRequestsWithPayment(self._session_factory(), client)

    def fetch_latest_issue(self) -> LatestIssue:
        """Run the guarded flow once and return the issue with its proof."""
        if self._settlements_attempted >= self.max_settlements:
            raise SessionBudgetExceeded(
                f"per process budget of {self.max_settlements} settlements is spent; "
                "nothing signed"
            )
        # Steps 1 and 2: read the live offer and verify it before signing.
        terms = read_offer(self._session_factory(), timeout=30)
        verify_terms(terms, expected_pay_to=self.expected_pay_to)
        # Step 3: exactly one attempt. The count is taken before the
        # attempt so a failure still consumes budget, per the seller's
        # suggested spend policy.
        self._settlements_attempted += 1
        session = self._payment_session_factory()
        response = session.get(FEED_URL, timeout=self.timeout)
        if response.status_code != 200:
            raise FeedError(
                f"feed answered HTTP {response.status_code} after the settlement "
                "attempt; the attempt is not retried"
            )
        body = response.json()
        issue = body.get("issue", body)
        # Step 4: settlement record plus the issue hash check.
        settlement = self._decode(response.headers.get("PAYMENT-RESPONSE"))
        return LatestIssue(
            issue=issue,
            terms=terms,
            settlement=settlement,
            integrity_ok=verify_issue_integrity(issue),
        )


def fetch_latest_issue(private_key: str, **client_kwargs) -> LatestIssue:
    """Convenience wrapper: build a client and fetch once."""
    return SignalFeedClient(private_key, **client_kwargs).fetch_latest_issue()
