"""Offline tests for the issue summary, hash check, and guard."""

import unittest

from feedfixtures import sample_issue

from agenttrust_signal_context.context import (
    GuardPolicy,
    evaluate_guard,
    summarize_issue,
    verify_issue_integrity,
)


class IntegrityTest(unittest.TestCase):
    def test_untouched_issue_verifies(self):
        self.assertTrue(verify_issue_integrity(sample_issue()))

    def test_tampered_issue_fails(self):
        issue = sample_issue()
        issue["indicators"]["btc_trend"]["state"] = "OFF"
        self.assertFalse(verify_issue_integrity(issue))

    def test_issue_without_integrity_block(self):
        issue = sample_issue()
        del issue["integrity"]
        self.assertIsNone(verify_issue_integrity(issue))


class SummarizeTest(unittest.TestCase):
    def test_labels_are_reduced(self):
        context = summarize_issue(sample_issue())
        self.assertEqual(context.btc_trend_state, "ON")
        self.assertEqual(context.alt_positive_count, 6)
        self.assertEqual(context.alt_universe_count, 9)
        self.assertTrue(context.equity_spy_above_sma200)
        self.assertEqual(context.equity_vix_term_structure, "CALM")
        self.assertEqual(context.mean_reversion_action, "STAY_FLAT")
        self.assertEqual(context.mstr_btc_filter_state, "OFF")
        self.assertIn("PAPER", context.disclaimer)


class GuardTest(unittest.TestCase):
    def setUp(self):
        self.context = summarize_issue(sample_issue())

    def test_no_conditions_proceeds(self):
        decision = evaluate_guard(self.context, GuardPolicy())
        self.assertTrue(decision.proceed)
        self.assertEqual(decision.reasons, [])

    def test_met_conditions_proceed(self):
        policy = GuardPolicy(
            require_btc_trend_on=True,
            block_on_vix_stress=True,
            require_equity_above_sma200=True,
            min_alt_positive=5,
        )
        decision = evaluate_guard(self.context, policy)
        self.assertTrue(decision.proceed)
        self.assertEqual(len(decision.reasons), 4)

    def test_btc_off_stands_aside(self):
        issue = sample_issue()
        issue["indicators"]["btc_trend"]["state"] = "OFF"
        context = summarize_issue(issue)
        decision = evaluate_guard(context, GuardPolicy(require_btc_trend_on=True))
        self.assertFalse(decision.proceed)

    def test_vix_stress_stands_aside(self):
        issue = sample_issue()
        issue["indicators"]["us_equity_regime"]["vix_term_structure"] = "STRESS"
        context = summarize_issue(issue)
        decision = evaluate_guard(context, GuardPolicy(block_on_vix_stress=True))
        self.assertFalse(decision.proceed)

    def test_breadth_below_minimum_stands_aside(self):
        decision = evaluate_guard(self.context, GuardPolicy(min_alt_positive=7))
        self.assertFalse(decision.proceed)

    def test_missing_label_fails_closed(self):
        issue = sample_issue()
        del issue["indicators"]["btc_trend"]
        context = summarize_issue(issue)
        decision = evaluate_guard(context, GuardPolicy(require_btc_trend_on=True))
        self.assertFalse(decision.proceed)
        self.assertIn("fails closed", decision.reasons[0])


if __name__ == "__main__":
    unittest.main()
