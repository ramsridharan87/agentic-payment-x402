# Agentic Payments Project — Build Brief

## The Idea
Build an AI agent that can autonomously pay for small, paywalled content (e.g. a $0.50 New Yorker article) on my behalf — read the request, fund the payment from a crypto wallet it controls, execute the payment through whatever rail the merchant actually accepts, and complete the task (e.g. summarize the article).

**Key reframe from initial idea:** x402 (Coinbase's HTTP 402-based payment protocol) is NOT assumed to be the only rail. Most legacy paywalls (New Yorker, Conde Nast, etc.) do not speak x402 — it's mainly used by crypto-native APIs/platforms today. So the architecture should support **two payment paths**:
1. **x402 direct path** — for the (currently small) set of merchants/APIs that support it natively. Fast, no card needed.
2. **Fiat bridge path** — for everything else. Convert USDC → a spendable virtual card in real time (via Lithic or similar), then complete a normal card checkout via browser automation.

---

## Core Components

| Component | Role | Candidate Tool |
|---|---|---|
| Wallet & funding | Holds USDC, agent-controlled | Coinbase Developer Platform (CDP) wallet, on Base chain |
| Stablecoin→fiat off-ramp | Converts USDC to a spendable card for fiat-only merchants | Lithic (virtual card issuing API) |
| Agent reasoning | Decides what/when/how much to pay, orchestrates tool calls | Claude API with tool use, built in Python (not a no-code tool like n8n — need tight control over money-triggering logic) |
| Browser automation | Actually navigates paywall pages, submits card, reads article | Playwright |
| x402 path | Skips the card step for protocol-native merchants | x402 SDK/middleware |
| Guardrails | Hard limits independent of agent's own reasoning | Custom code layer — per-transaction cap, daily/session cap |
| Secrets management | Protects API keys/credentials | Env vars locally → proper secrets manager (AWS Secrets Manager, Render env vars) once deployed |
| Endpoint auth | Prevents randoms from triggering the agent and burning credits/funds | Private API key gating my own trigger endpoint |
| Deployment | Makes this usable from anywhere, not just my laptop | Local Playwright/Python first → deploy to Render/Railway/Browserbase-style host for 24/7 headless operation |

---

## Key Architectural Principle: Separation of Reasoning and Custody
- The LLM (the "agent") never directly holds or sees the wallet's raw API credentials.
- The agent can only call a **narrow, pre-defined function** (e.g. `make_payment(amount, destination)`).
- That function — plain code, not the LLM — is the only thing that touches Coinbase/Lithic credentials.
- This function enforces hard spending caps regardless of what the LLM "decides."

Mental model: the agent is a decision-maker behind a locked door; it can only ask a tightly scoped assistant to perform specific pre-approved actions.

---

## Suggested Build Order (with rationale)

**1. CDP wallet creation & funding (start here)**
- New to me: first wallet not held in my own name/custody — fully assigned to agent control. Worth doing deliberately, slowly.
- Fund with a small trivial amount first: **$10 USDC**, not $50. Small enough to treat as a real experiment without real risk.
- Goal: understand wallet creation, funding, and what "agent-controlled" actually means before any agent logic exists.

**2. Lithic off-ramp, in isolation**
- Build a standalone script: take a dollar amount → pull USDC from CDP wallet → produce a working one-time virtual card number.
- Rationale for testing this early and in isolation:
  - Highest external/compliance uncertainty (Lithic onboarding, KYB, whether crypto-funded card issuing is smooth) — surface this risk early.
  - Binary, unambiguous success/failure (you either get a working card or you don't).
  - Everything else in this project (API orchestration, decision logic) is closer to my existing day-job skill set — this is the genuinely novel part.

**3. Agent reasoning loop**
- Python + Claude API with tool/function calling.
- Define a small set of tools: e.g. `check_price`, `request_payment`, `fetch_page_content`.
- Model reasons in natural language ("price is $0.50, I should pay"), outputs a structured tool call, code executes it.

**4. Browser automation (Playwright)**
- Playwright drives a real (or headless) browser: navigate to URL, read page content, click, type, submit card details.
- Agent decides *what* should happen at a high level; code translates that into actual Playwright actions.
- Local Chrome window for dev/debugging → headless Chromium once deployed.

**5. Security & guardrails layer**
- Secrets: env vars → real secrets manager once hosted.
- Endpoint auth: private key required to trigger the agent at all.
- Spending caps: hard-coded, enforced in code (not just prompted) —
  - Per-transaction cap (e.g. never >$2 without explicit confirmation)
  - Daily/session cap (e.g. never >$X or >N transactions per day) — protects against a buggy loop firing repeated payments.
- Logging/audit trail: record every decision + transaction outside of just the model's own narration.

**6. x402 path (bonus, not blocking)**
- Add support for merchants/APIs that natively speak x402 — skips the Lithic/card step entirely for those.
- Nice-to-have optimization layered on top of the fiat-bridge path, not a dependency for launch.

**7. Deployment**
- Prototype and validate fully locally first.
- Once working, deploy to a small always-on host (Render, Railway, or similar) so the agent is internet-usable and triggerable from anywhere (e.g. phone).

---

## Open Questions to Resolve During Build
- Lithic's onboarding/KYB requirements for an individual builder vs. a registered business.
- Exact CDP wallet funding flow (on-ramp from exchange → Base chain USDC).
- What specific spending cap numbers make sense for real testing (e.g. $2 per-tx / $10 per day to start).
- Whether to browser-automate against a specific first test target, or start with a merchant/API known to support card payments cleanly for the first end-to-end test.

---

## First Milestone
Get a working script that: creates/confirms a CDP wallet funded with $10 USDC → calls Lithic to mint a one-time virtual card for a specified small amount → prints back a usable card number. No agent reasoning, no browser automation yet — just prove the money-movement mechanics work.
