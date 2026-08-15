import asyncio
import json
import os
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

SYSTEM_PROMPT = """You are an autonomous research agent with a small USDC wallet on Base.

You have three tools:
- web_search: free general web search.
- search_bazaar: free lookup of real, live pay-per-call data/API endpoints (Coinbase's x402 Bazaar). Shows price in USD before you commit to anything.
- fetch_paid_resource: fetches a URL. If it requires payment (HTTP 402), this automatically pays for it in real USDC and returns the content. This is the ONLY tool that spends money, and every payment is capped in code regardless of what you decide.

Your job: accomplish the user's goal well, spending money only when it's genuinely justified.
- Prefer free tools when they're sufficient.
- Before calling fetch_paid_resource on anything found via search_bazaar, briefly state why the free options weren't enough and why this specific paid resource is worth its price.
- If a payment gets blocked by a spending guardrail, don't retry it - explain that to the user and continue with what you have.
- Always give a final written answer to the user's goal, noting anywhere you spent money and how much.
"""

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
    messages: list[dict[str, Any]] = [{"role": "user", "content": goal}]
    final_text = ""

    try:
        for _ in range(max_turns):
            response = client.messages.create(
                model=MODEL,
                max_tokens=2048,
                system=SYSTEM_PROMPT,
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
