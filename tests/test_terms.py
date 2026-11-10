"""Offline tests for the 402 offer parsing and term checks."""

import unittest

from feedfixtures import offer_header

from agenttrust_signal_context.terms import (
    EXPECTED_PAY_TO,
    TermsMismatch,
    parse_payment_required,
    verify_terms,
)


class ParseOfferTest(unittest.TestCase):
    def test_parses_live_shaped_offer(self):
        terms = parse_payment_required(offer_header())
        self.assertEqual(terms.scheme, "exact")
        self.assertEqual(terms.network, "eip155:8453")
        self.assertEqual(terms.amount_atomic, "40000")
        self.assertEqual(terms.pay_to, EXPECTED_PAY_TO)
        self.assertEqual(terms.asset_name, "USD Coin")

    def test_missing_header_fails_closed(self):
        with self.assertRaises(TermsMismatch):
            parse_payment_required(None)
        with self.assertRaises(TermsMismatch):
            parse_payment_required("")

    def test_undecodable_header_fails_closed(self):
        with self.assertRaises(TermsMismatch):
            parse_payment_required("not-base64-json!!!")


class VerifyTermsTest(unittest.TestCase):
    def test_published_terms_pass(self):
        verify_terms(parse_payment_required(offer_header()))

    def test_each_field_is_checked(self):
        bad_offers = [
            {"scheme": "upto"},
            {"network": "eip155:1"},
            {"asset": "0x0000000000000000000000000000000000000000"},
            {"amount": "200000"},
            {"amount": "99999"},
            {"payTo": "0x0000000000000000000000000000000000000001"},
        ]
        for overrides in bad_offers:
            with self.subTest(overrides=overrides):
                with self.assertRaises(TermsMismatch):
                    verify_terms(parse_payment_required(offer_header(**overrides)))

    def test_pay_to_override_is_respected(self):
        other = "0x0000000000000000000000000000000000000002"
        terms = parse_payment_required(offer_header(payTo=other))
        verify_terms(terms, expected_pay_to=other)
        with self.assertRaises(TermsMismatch):
            verify_terms(terms)


if __name__ == "__main__":
    unittest.main()
