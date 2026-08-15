# Agentic Payments Project — Build Brief

## The Idea
Build an AI agent that can autonomously decide when a task requires paying for a resource, and pay for it on my behalf — reasoning about the decision itself, not just executing a payment I've already told it to make.

This project serves two learning goals, pursued as two separate, sequential experiments:

1. **Learn to build an agentic payments tool end-to-end that reasons about whether to make a payment** — Experiment 1, active now.
2. **Learn to use fiat to make payments** — Experiment 2, deferred until Experiment 1 is done.

---

## Experiment 1: x402 Agentic Payments (Active — Build This Weekend)

**Goal:** build a goal-driven agent that autonomously decides whether a task requires a paid resource, and if so, pays for it via x402 in real USDC on Base — no fiat, no card issuance, no browser automation involved at all.

**Wallet:** reuse the existing CDP wallet, already funded with real USDC on Base mainnet. The existing $2-per-transaction Wallet Policy (`netUSDChange <= 200 cents`) stays enforced as a guardrail independent of the agent's own reasoning.

**Critical requirement:** the agent must do its own reasoning about whether to pay — it is not directly orchestrated by me calling a specific paid endpoint. It needs both free tools (e.g. web search) and paid x402 tools/endpoints available to it, must discover through the task itself when it's hit a 402 response, and must then decide autonomously whether the task justifies paying.

**Source of paid resources:** Coinbase's **x402 Bazaar** — a live, searchable directory of real pay-per-call endpoints (financial data, AI inference, scraping, etc.).

**Candidate goals** (build incrementally, not all at once):
1. Determine current Bitcoin market sentiment and summarize in one paragraph — free search may suffice, or the agent may reach for a paid data/sentiment API.
2. Get the latest price of a specified stock and flag anything unusual — maps to Bazaar financial data endpoints.
3. General research task where Parcl Labs' real estate API may surface as a free/subscription comparison point, but any paid step taken should come from x402 Bazaar-listed alternatives.

**Build phases:**
- **Phase 1 (this weekend):** single goal, agent has both free and paid tools available, must reason and decide independently whether to pay.
- **Later phases (not this weekend):** explicit spending-policy language given to the agent, and multi-option price/quality comparison across paid alternatives before choosing one.

---

## Experiment 2: Fiat Card Issuance (Deferred — Sandbox Only)

**Goal:** prove the full fiat-card architecture and agent decision logic end-to-end, in **sandbox only** — Lithic or Rain sandbox, whichever has the cleaner dev experience.

**Retired for this experiment:** unlocking a real, live New Yorker article, in its current form. Lithic requires a funding account (e.g. a linked bank account) and cannot pull funds directly from a crypto wallet — bridging USDC into a Lithic-funded card requires a human-mediated bank-linking step. That breaks the fully agentic nature of the flow: the funding source can't be created or linked by the agent itself, no matter how the reasoning layer is built. This is a structural limitation of the funding model, not just a KYB/business-approval hurdle (though that applies too, for production access). This experiment validates the mechanics and architecture in sandbox, not a live real-money outcome.

**Guardrails carry over unchanged:** separation of agent reasoning from wallet custody, hard spending caps, audit logging — all still apply, just validated against simulated/sandbox transactions instead of real ones.

---

## Key Architectural Principle: Separation of Reasoning and Custody
- The LLM (the "agent") never directly holds or sees the wallet's raw API credentials.
- The agent can only call a **narrow, pre-defined function** (e.g. `make_payment(amount, destination)`).
- That function — plain code, not the LLM — is the only thing that touches Coinbase/Lithic credentials.
- This function enforces hard spending caps regardless of what the LLM "decides."

Mental model: the agent is a decision-maker behind a locked door; it can only ask a tightly scoped assistant to perform specific pre-approved actions.

---

## Security & Guardrails
- **Secrets:** env vars locally → proper secrets manager once hosted.
- **Endpoint auth:** private key required to trigger the agent at all.
- **Spending caps:** hard-coded, enforced in code (not just prompted) —
  - Per-transaction cap (e.g. never >$2 without explicit confirmation) — currently enforced for Experiment 1 via the CDP Wallet Policy (`netUSDChange <= 200 cents`).
  - Daily/session cap (e.g. never >$X or >N transactions per day) — protects against a buggy loop firing repeated payments.
- **Logging/audit trail:** record every decision + transaction outside of just the model's own narration.

These guardrails apply to both experiments, whether the transaction is real (Experiment 1) or simulated (Experiment 2).
