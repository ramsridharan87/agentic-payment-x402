# Agentic Payments

An agent that autonomously decides when a task needs a paid resource, and pays for it — reasoning about the decision itself, not just executing a payment it's been told to make. See [agentic-payments-project-brief.md](agentic-payments-project-brief.md) for the full design.

Two sequential experiments:
- **Experiment 1** (built, working): the agent reasons about whether to pay, and if so pays via **x402** in real USDC on Base, sourced from Coinbase's x402 Bazaar. No fiat, no cards.
- **Experiment 2** (deferred): fiat card issuance (Lithic/Rain), sandbox only.

The LLM never touches wallet credentials. It can only call `fetch_paid_resource`, a narrow function that enforces hard per-transaction and daily spending caps in code before any signature is produced — independent of whatever the model decides. The CDP wallet itself also enforces a $2/transaction Wallet Policy server-side, so a bug in this code isn't the only line of defense.

## Setup

Uses a dedicated conda environment (`agentic-payments`, Python 3.11) since the system default Python (Anaconda base, 3.6) is too old for the CDP/Anthropic SDKs.

```
conda activate agentic-payments
pip install -e ".[wallet,payments,tools,ui,agent,documents,dev]"
cp .env.example .env   # then fill in real keys, including TRIGGER_API_KEY
```

Required accounts/keys: a CDP Secret API Key + Wallet Secret ([portal.cdp.coinbase.com/access/api](https://portal.cdp.coinbase.com/access/api)), an Anthropic API key, and a CDP wallet funded with a small amount of USDC on Base.

## Running it

```
# Confirm the wallet and its balance
python scripts/wallet_status.py

# Run one goal from the command line
python scripts/run_agent.py "Determine current Bitcoin market sentiment and summarize it in one paragraph."

# Or run the dashboard and submit goals from the browser
uvicorn agentic_payments.ui.app:app --reload
```

The dashboard (`/`) lists every run with total spend; `/new` submits a new goal (runs in the background, page auto-refreshes while running); each run page shows the full reasoning/tool-call/payment timeline plus a PDF download of the final answer; `/purchases` shows every payment across all runs with amount, destination, and tx hash. Every route except `/healthz` requires the `TRIGGER_API_KEY` password (HTTP Basic Auth) - the app refuses to start without it set, since it can trigger real payments.

## Deployment (Render)

`render.yaml` is a Render Blueprint: a `starter`-plan web service with a 1GB persistent disk (mounted at `/var/data`, holding the SQLite audit log and generated PDFs - the free tier has no persistent disk, so runs/spend history won't survive a restart on it). Connect the GitHub repo in the Render dashboard, and it picks up `render.yaml` automatically. Secrets (`CDP_API_KEY_ID`, `CDP_API_KEY_SECRET`, `CDP_WALLET_SECRET`, `ANTHROPIC_API_KEY`, `TRIGGER_API_KEY`) are marked `sync: false` in the blueprint, so Render prompts for them in its dashboard rather than storing them in the repo.

## Build order

1. CDP wallet creation & funding - done
2. Agent reasoning loop (Claude API + tool use) with free web search, free Bazaar search, and paid `fetch_paid_resource` - done
3. Guardrails: spending caps, endpoint auth, audit logging - done
4. UI: goal submission, run timeline, purchase log, PDF export - done
5. Hosted deployment (Render)
6. Experiment 2 (fiat card issuance, sandbox only) - deferred
