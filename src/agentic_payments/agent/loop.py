import asyncio
import json
import os
from datetime import datetime, timezone
from typing import Any

from anthropic import Anthropic
from cdp import CdpClient

from ..audit import AuditLog
from ..documents import generate_pdf
from ..guardrails import SpendingPolicy
from ..net import force_ipv4
from ..payments.signer import CdpEvmSigner
from ..payments.x402_client import LastPayment, build_x402_client
from ..tools.bazaar import search_bazaar
from ..tools.fetch_paid import fetch_paid_resource
from ..tools.web_search import web_search
from ..wallet.cdp_wallet import get_or_create_wallet

MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-5")

SYSTEM_PROMPT_TEMPLATE = """You are an autonomous research agent with a small USDC wallet on Base.

Today's date is {today} (UTC). Treat this as ground truth for "now." Do not infer or override it from search results, tool timestamps, training data, or old sources claiming otherwise - free search is frequently stale, so a source disagreeing with the date above means the source is old, not that this date is wrong. If a paid/live tool result is timestamped close to the date above, that is a sign the data is current, not a malfunction.

You have three tools:
- web_search: free general web search.
- search_bazaar: free lookup of real, live pay-per-call data/API endpoints (Coinbase's x402 Bazaar). Shows price in USD before you commit to anything.
- fetch_paid_resource: fetches a URL. If it requires payment (HTTP 402), this automatically pays for it in real USDC and returns the content. This is the ONLY tool that spends money, and every payment is capped in code regardless of what you decide.

Your job: accomplish the user's goal well, spending money only when it's genuinely justified.
- Prefer free tools when they're sufficient.
- Before calling fetch_paid_resource on anything found via search_bazaar, briefly state why the free options weren't enough and why this specific paid resource is worth its price.
- If a payment gets blocked by a spending guardrail, don't retry it - explain that to the user and continue with what you have.

## When free search keeps failing on a live fact

Some sub-questions are inherently time-sensitive: a current price, whether something is depegged/down/live right now, "as of today." Free web search returns snapshots that are often stale, cached, or contradict each other for exactly these questions - that's not a sign you searched wrong, it's a structural limit of free search for live data.

Treat repetition as a signal, not a reason to keep trying the same way. If you've made several differently-phrased searches (roughly 3-4) for the *same specific live fact* and you're still getting dated, conflicting, or unconfirmed snapshots, stop reformulating the search. Instead, reason about it explicitly, out loud, before deciding what to do next - something like: "Free search keeps returning outdated or conflicting values for [X]. A paid live-data source would resolve this directly. Given the goal, is that cost justified?" Then actually make that call: check search_bazaar for a live source and weigh its price against how much the goal depends on that fact being current, rather than letting the search count grow indefinitely.

## Calibrating confidence for live facts

Never state a time-sensitive fact (a price, a live status, "is X still true today") with more confidence than your evidence supports. Before writing any such claim in your final answer, check what your most recent evidence for it actually is:
- If it's a paid live-data source you just fetched: state it as current.
- If it's a free-search snippet with a clear, recent timestamp that matches "now": state it, but note the source/timestamp.
- If your most recent evidence is dated, ambiguous, or contradicted by other sources, say so directly in the answer instead of picking a number and presenting it as fact - e.g. "the most recent figure I found was dated [X] and I could not confirm it reflects the current state" rather than stating a specific current value. This applies whether or not you looked for a paid source - the point is your stated confidence should never exceed what you actually know.

Always give a final written answer to the user's goal, noting anywhere you spent money and how much.
"""


def _build_system_prompt() -> str:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return SYSTEM_PROMPT_TEMPLATE.format(today=today)


TOOLS: list[dict[str, Any]] = [
    {
        "name": "web_search",
        "description": "Free general web search. Returns title/url/snippet for each result.",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    },
    {
        "name": "search_bazaar",
        "description": (
            "Free search of Coinbase's x402 Bazaar for real paid API endpoints matching "
            "a query. Shows price in USD. Does not pay for or call anything."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "max_usd_price": {
                    "type": "number",
                    "description": "Optional price ceiling in USD",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "fetch_paid_resource",
        "description": (
            "Fetch a URL, automatically paying via x402 in real USDC if it requires "
            "payment (HTTP 402). The only tool that spends money."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"url": {"type": "string"}},
            "required": ["url"],
        },
    },
]


def _wallet_address() -> str:
    async def fetch() -> str:
        async with CdpClient() as cdp:
            account = await get_or_create_wallet(cdp)
            return account.address

    return asyncio.run(fetch())


def _run_tool(
    name: str,
    tool_input: dict[str, Any],
    x402_client,
    audit: AuditLog,
    last_payment: LastPayment,
) -> dict[str, Any]:
    audit.log(
        "tool_call", f"{name}({json.dumps(tool_input)})", tool_name=name, detail=tool_input
    )

    if name == "web_search":
        return {"results": web_search(tool_input["query"])}
    if name == "search_bazaar":
        return {
            "results": search_bazaar(
                tool_input["query"], max_usd_price=tool_input.get("max_usd_price")
            )
        }
    if name == "fetch_paid_resource":
        return fetch_paid_resource(tool_input["url"], x402_client, audit, last_payment)

    return {"error": f"Unknown tool: {name}"}


def run_agent(goal: str, run_id: str | None = None, max_turns: int = 12) -> str:
    """Run the agent on `goal` to completion, returning its final answer.
    Every reasoning step, tool call, and payment decision is written to the
    audit log as it happens. Pass `run_id` when the caller (e.g. the UI)
    needs to know the id before the run finishes."""
    force_ipv4()

    audit = AuditLog(run_id=run_id) if run_id else AuditLog()
    audit.start_run(goal)

    policy = SpendingPolicy.from_env()
    signer = CdpEvmSigner(_wallet_address())
    x402_client, last_payment = build_x402_client(
        signer, audit, policy.per_tx_cap_usd, policy.daily_cap_usd
    )

    client = Anthropic()
    system_prompt = _build_system_prompt()
    messages: list[dict[str, Any]] = [{"role": "user", "content": goal}]
    final_text = ""

    try:
        for _ in range(max_turns):
            response = client.messages.create(
                model=MODEL,
                max_tokens=4096,
                system=system_prompt,
                tools=TOOLS,
                messages=messages,
            )

            for block in response.content:
                if block.type == "text" and block.text.strip():
                    audit.log("reasoning", block.text.strip())
                    final_text = block.text.strip()

            messages.append({"role": "assistant", "content": response.content})

            if response.stop_reason != "tool_use":
                break

            tool_results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue
                result = _run_tool(block.name, block.input, x402_client, audit, last_payment)
                tool_results.append(
                    {"type": "tool_result", "tool_use_id": block.id, "content": json.dumps(result)}
                )
            messages.append({"role": "user", "content": tool_results})

        audit.log("final_answer", final_text)
        if final_text:
            generate_pdf(audit.run_id, goal, final_text)
        audit.end_run("completed")
    except Exception as exc:
        audit.log("error", str(exc))
        audit.end_run("failed")
        raise

    return final_text
