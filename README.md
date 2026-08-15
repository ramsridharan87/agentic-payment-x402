# Agentic Payments

An agent that autonomously pays small paywall fees on my behalf — e.g. unlocking a $0.50 article — funded from a crypto wallet it controls. See [agentic-payments-project-brief.md](agentic-payments-project-brief.md) for the full design.

Two payment paths: **x402** for merchants that speak it natively, and a **fiat bridge** (USDC → Lithic virtual card → normal checkout) for everything else. The LLM never touches raw wallet/card credentials — it only calls narrow, pre-defined functions that enforce hard spending caps in code.

## Setup

Uses a dedicated conda environment (`agentic-payments`, Python 3.11) since the system default Python (Anaconda base, 3.6) is too old for the CDP/Playwright/Anthropic SDKs.

```
conda activate agentic-payments
pip install -e ".[wallet,offramp,agent,browser,dev]"
cp .env.example .env   # then fill in real keys
```

## Build order

1. CDP wallet creation & funding ($10 USDC)
2. Lithic off-ramp (USDC → one-time virtual card), in isolation
3. Agent reasoning loop (Claude API + tool use)
4. Browser automation (Playwright)
5. Guardrails: spending caps, endpoint auth, audit logging
6. x402 path (bonus)
7. Deployment

Step 1 done: `scripts/wallet_status.py` creates/confirms the CDP wallet and reports its Base-mainnet USDC balance. Currently at: **step 2** (Lithic off-ramp).
