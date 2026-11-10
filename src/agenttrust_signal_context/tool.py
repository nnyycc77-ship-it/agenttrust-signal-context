"""LangChain tool: Signal Feed regime context as a pre-decision check.

The tool fetches the latest Signal Feed issue through the guarded
client in client.py, reduces it to its regime labels, and evaluates a
caller supplied policy before the agent acts. The answer is the
context, the guard decision with a reason for every check, and the
settlement record of the call, so the decision an agent makes next is
traceable to the exact issue it read.
"""

from __future__ import annotations

import asyncio
import json
import os
from typing import Optional, Type

from langchain_core.callbacks import (
    AsyncCallbackManagerForToolRun,
    CallbackManagerForToolRun,
)
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from .client import SignalFeedClient
from .context import GuardPolicy, evaluate_guard, summarize_issue


class SignalFeedContextInput(BaseModel):
    """Guard conditions, all optional; an unset condition is not checked."""

    require_btc_trend_on: bool = Field(
        default=False, description="Proceed only when the BTC trend label is ON."
    )
    block_on_vix_stress: bool = Field(
        default=False,
        description="Stand aside when the VIX term structure label is STRESS.",
    )
    require_equity_above_sma200: bool = Field(
        default=False, description="Proceed only when SPY is above its SMA200."
    )
    min_alt_positive: Optional[int] = Field(
        default=None,
        description="Minimum number of altcoins with a positive trend score (of 9).",
    )


def fetch_context(private_key: str, policy: GuardPolicy, **client_kwargs) -> dict:
    """Fetch the latest issue and evaluate the policy against it."""
    result = SignalFeedClient(private_key, **client_kwargs).fetch_latest_issue()
    context = summarize_issue(result.issue)
    decision = evaluate_guard(context, policy)
    return {
        "context": context.to_dict(),
        "decision": decision.to_dict(),
        "settlement": result.settlement.to_dict() if result.settlement else None,
        "integrity_ok": result.integrity_ok,
        "issue": result.issue,
    }


class SignalFeedContextTool(BaseTool):
    """Read the Signal Feed market regime as a pre-decision check.

    Returns the feed's rule based labels (BTC trend, altcoin trend
    breadth, US equity regime, SPY mean reversion state, MSTR BTC
    filter), a proceed or stand aside decision against the guard
    conditions passed in, and the settlement record of the call. The
    labels are context from the publisher's virtual research accounts,
    not advice and not a forecast.
    """

    name: str = "signal_feed_regime_context"
    description: str = (
        "Fetch the Signal Feed daily market regime issue over x402 on Base "
        "and evaluate it as a pre-decision context check: BTC trend ON or OFF, "
        "altcoin trend breadth across 9 coins, US equity regime (SPY vs SMA200, "
        "VIX term structure CALM or STRESS), SPY mean reversion state and the "
        "MSTR BTC filter. Pass guard conditions (require the BTC trend ON, "
        "stand aside on VIX STRESS, require SPY above SMA200, minimum altcoin "
        "breadth) and get back the labels, a proceed or stand aside decision "
        "with reasons, and the settlement record. Use before an agent acts, "
        "as context for the decision, never as a prediction."
    )
    args_schema: Type[BaseModel] = SignalFeedContextInput

    private_key_env: str = Field(default="AGENT_PRIVATE_KEY")

    def _private_key(self) -> str:
        key = os.environ.get(self.private_key_env, "")
        if not key:
            raise ValueError(
                f"{self.private_key_env} is not set. Set it to the key of a "
                "dedicated wallet holding a small USDC balance on Base."
            )
        return key

    def _run(
        self,
        require_btc_trend_on: bool = False,
        block_on_vix_stress: bool = False,
        require_equity_above_sma200: bool = False,
        min_alt_positive: Optional[int] = None,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        policy = GuardPolicy(
            require_btc_trend_on=require_btc_trend_on,
            block_on_vix_stress=block_on_vix_stress,
            require_equity_above_sma200=require_equity_above_sma200,
            min_alt_positive=min_alt_positive,
        )
        return json.dumps(fetch_context(self._private_key(), policy), indent=2)

    async def _arun(
        self,
        require_btc_trend_on: bool = False,
        block_on_vix_stress: bool = False,
        require_equity_above_sma200: bool = False,
        min_alt_positive: Optional[int] = None,
        run_manager: Optional[AsyncCallbackManagerForToolRun] = None,
    ) -> str:
        return await asyncio.to_thread(
            self._run,
            require_btc_trend_on,
            block_on_vix_stress,
            require_equity_above_sma200,
            min_alt_positive,
            None,
        )


__all__ = ["SignalFeedContextTool", "SignalFeedContextInput", "fetch_context"]
