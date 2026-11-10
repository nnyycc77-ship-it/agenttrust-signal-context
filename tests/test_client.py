"""Offline tests for the guarded client flow, using fake sessions.

No network and no wallet: the payment session is a stub, and the key
used here is a throwaway test value that never leaves this file.
"""

import unittest

from feedfixtures import offer_header, sample_issue

from agenttrust_signal_context.client import (
    FeedError,
    SessionBudgetExceeded,
    SettlementProof,
    SignalFeedClient,
    read_offer,
)
from agenttrust_signal_context.terms import TermsMismatch

TEST_KEY = "0x" + "11" * 32  # throwaway, not a wallet


class FakeResponse:
    def __init__(self, status_code, headers=None, body=None):
        self.status_code = status_code
        self.headers = headers or {}
        self._body = body or {}

    def json(self):
        return self._body


class FakeSession:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def get(self, url, timeout=None):
        self.calls.append(url)
        return self._responses.pop(0)


def offer_session(**overrides):
    return FakeSession(
        [FakeResponse(402, headers={"Payment-Required": offer_header(**overrides)})]
    )


def stub_decoder(_header):
    return SettlementProof(
        success=True,
        payer="0x2D98EE4949F391f957d10588C00D467AB1749fCe",
        network="eip155:8453",
        transaction="0x" + "ab" * 32,
        amount_atomic="40000",
    )


class ReadOfferTest(unittest.TestCase):
    def test_reads_offer_from_402(self):
        terms = read_offer(offer_session())
        self.assertEqual(terms.amount_atomic, "40000")

    def test_non_402_answer_stops_the_call(self):
        with self.assertRaises(FeedError):
            read_offer(FakeSession([FakeResponse(200, body={})]))


class FetchFlowTest(unittest.TestCase):
    def make_client(self, plain, payment, **kwargs):
        return SignalFeedClient(
            TEST_KEY,
            session_factory=lambda: plain,
            payment_session_factory=lambda: payment,
            settlement_decoder=stub_decoder,
            **kwargs,
        )

    def test_happy_path_returns_issue_with_proof(self):
        plain = offer_session()
        payment = FakeSession(
            [FakeResponse(200, headers={"PAYMENT-RESPONSE": "stub"}, body={"issue": sample_issue()})]
        )
        client = self.make_client(plain, payment)
        result = client.fetch_latest_issue()
        self.assertEqual(result.issue["feed"], "regime-feed")
        self.assertTrue(result.integrity_ok)
        self.assertEqual(result.settlement.amount_atomic, "40000")
        self.assertEqual(len(payment.calls), 1)  # exactly one attempt

    def test_terms_mismatch_signs_nothing(self):
        plain = offer_session(payTo="0x0000000000000000000000000000000000000001")
        payment = FakeSession([])
        client = self.make_client(plain, payment)
        with self.assertRaises(TermsMismatch):
            client.fetch_latest_issue()
        self.assertEqual(payment.calls, [])

    def test_failed_attempt_is_not_retried(self):
        plain = offer_session()
        payment = FakeSession([FakeResponse(500)])
        client = self.make_client(plain, payment)
        with self.assertRaises(FeedError):
            client.fetch_latest_issue()
        self.assertEqual(len(payment.calls), 1)

    def test_budget_is_enforced(self):
        plain = offer_session()
        payment = FakeSession(
            [FakeResponse(200, headers={"PAYMENT-RESPONSE": "stub"}, body={"issue": sample_issue()})]
        )
        client = self.make_client(plain, payment, max_settlements=1)
        client.fetch_latest_issue()
        with self.assertRaises(SessionBudgetExceeded):
            client.fetch_latest_issue()
        self.assertEqual(len(payment.calls), 1)


if __name__ == "__main__":
    unittest.main()
