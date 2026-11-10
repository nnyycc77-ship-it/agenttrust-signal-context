# Signal Feed regime context for LangChain

A pre-decision context check for agents, built on the
[Signal Feed API](https://signals.agenttrustapi.com/offers): before an
agent acts, it reads the feed's daily market regime issue through the
x402 protocol on Base and evaluates the labels against guard
conditions the caller sets. No account and no API key.

One issue a day, the same for every reader, with five rule based
market state labels:

- BTC trend filter (daily close vs SMA20/50): ON or OFF
- Trend scores for 9 altcoins, as a breadth count
- US equity regime: SPY vs SMA200, and the VIX/VIX3M term structure
  (CALM or STRESS)
- SPY RSI(2) mean reversion state
- MSTR BTC filter: ON or OFF

The tool returns the labels, a proceed or stand aside decision with a
reason for every guard check, and the settlement record of the call,
so the action an agent takes next is traceable to the exact issue it
read.

The labels are context, not advice and not a forecast. The feed's
rules come from the publisher's own virtual (PAPER) research
accounts, its first issue was 2026-10-26, and it has no track record;
every issue carries that disclaimer and this tool passes it through
in its output. Nothing here places orders or connects to an exchange
or broker.

## How it works

1. The client requests `GET /v1/feed/latest` with a plain HTTP
   request and reads the 402 offer. Nothing is signed at this step.
2. The offer is checked field by field against the terms the
   publisher posts in its offers file: scheme `exact`, network Base
   (`eip155:8453`), asset USDC, amount 40000 (0.04 USDC), and the
   published recipient. Any difference stops the call before a
   signature exists.
3. Exactly one attempt follows, through the official `x402` Python
   SDK: the SDK signs a USDC `transferWithAuthorization` (EIP-3009,
   gasless for the caller) with the wallet in `AGENT_PRIVATE_KEY` and
   sends it with the request. A limit in the client caps any single
   settlement at 0.04 USDC, a per process budget caps settlements at
   two by default, and a failed attempt is never retried by this
   code.
4. The completed response carries the issue JSON plus a
   `PAYMENT-RESPONSE` header. The client decodes the header into a
   settlement record and recomputes the issue payload hash against
   the hash the issue carries, so a tampered or mismatched issue is
   visible in the result instead of being silently trusted.

Guard conditions are the caller's own rules, set per call: require
the BTC trend ON, stand aside when the VIX term structure reads
STRESS, require SPY above its SMA200, or require a minimum altcoin
breadth. A required check whose label is missing fails closed.

## Install

```bash
pip install git+https://github.com/nnyycc77-ship-it/agenttrust-signal-context
# or, from a clone:
pip install -e .
```

## Configure

Use a dedicated wallet holding a small USDC balance on Base. Never a
main wallet.

```bash
export AGENT_PRIVATE_KEY=0x...
```

The recipient the client will settle with is pinned to the
publisher's posted address. To follow a future change by the
publisher, set `SIGNAL_FEED_EXPECTED_PAY_TO` to the new address; the
term check then uses that value.

## Use it

```python
from agenttrust_signal_context.tool import SignalFeedContextTool

tool = SignalFeedContextTool()
print(tool.invoke({"require_btc_trend_on": True, "block_on_vix_stress": True}))
```

Framework free use works too:

```python
import os
from agenttrust_signal_context import GuardPolicy
from agenttrust_signal_context.tool import fetch_context

result = fetch_context(
    os.environ["AGENT_PRIVATE_KEY"],
    GuardPolicy(require_btc_trend_on=True, min_alt_positive=5),
)
print(result["decision"])  # {"proceed": ..., "reasons": [...]}
```

Or run the example, which prints the context, the decision, and the
settlement record, and runs a placeholder action only when the
decision is to proceed:

```bash
python examples/check_before_acting.py
```

## Live run status

The tool has been run against the production endpoint five times.

Three runs on 2026-11-06 read the 402 offer and verified its terms
against the published values, but the endpoint did not answer the
settled request within the client timeout (280 seconds on the later
runs). A direct ledger check after each run confirmed that no
transfer settled and no funds moved.

A run on 2026-11-09 stopped before any signature: the seller had
lowered the price in its offers file and in the live offer from
0.10 to 0.04 USDC, and the client failed closed on the changed
amount until its pinned terms were updated to the newly published
values.

The next run on 2026-11-09 completed end to end. The endpoint
answered in about 24 seconds, the issue payload hash verified, and
the settlement landed on Base in transaction
0x4491202653616cbec7e3b8541c9e1b4f8ebe2432b0295f1d8398644bd9c05c4d
(block 55445033): 40000 atomic units of USDC (0.04 USDC) from the
buyer wallet to the published recipient, confirmed from the
transaction receipt. The issue served was dated 2026-11-09.

## Development

The tests run offline against fixtures in the live shapes; they make
no network calls and sign nothing.

```bash
python -m unittest discover -s tests
```

## License

MIT
