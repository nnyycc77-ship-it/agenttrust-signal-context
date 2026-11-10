"""Run the pre-decision context check once and print the outcome.

Setup:
    pip install -e .
    export AGENT_PRIVATE_KEY=0x...   # dedicated wallet, a little USDC on Base

Run:
    python examples/check_before_acting.py

The example fetches the latest Signal Feed issue, evaluates a sample
guard policy, and prints the context, the decision with its reasons,
and the settlement record. The "action" at the end is a placeholder
print: it stands in for whatever the calling agent would do next, and
it only runs when the guard decision is to proceed.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from agenttrust_signal_context import GuardPolicy
from agenttrust_signal_context.tool import fetch_context


def main() -> None:
    policy = GuardPolicy(
        require_btc_trend_on=True,
        block_on_vix_stress=True,
        min_alt_positive=5,
    )
    result = fetch_context(_private_key(), policy)
    print(json.dumps(result, indent=2))
    if result["decision"]["proceed"]:
        print("\nGuard decision: proceed. The placeholder action would run now.")
    else:
        print("\nGuard decision: stand aside. The placeholder action is skipped.")


def _private_key() -> str:
    import os

    key = os.environ.get("AGENT_PRIVATE_KEY", "")
    if not key:
        raise SystemExit(
            "AGENT_PRIVATE_KEY is not set. Set it to the key of a dedicated "
            "wallet holding a small USDC balance on Base."
        )
    return key


if __name__ == "__main__":
    main()
