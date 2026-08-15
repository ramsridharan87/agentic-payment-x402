import asyncio
from pathlib import Path

from cdp import CdpClient
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from ..audit import AuditLog, fetch_events, fetch_run, fetch_runs
from ..guardrails import SpendingPolicy
from ..net import force_ipv4
from ..wallet.cdp_wallet import get_or_create_wallet

load_dotenv()
force_ipv4()

app = FastAPI(title="Agentic Payments - Decision Log")
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


def _resolve_wallet_address() -> str:
    async def fetch() -> str:
        async with CdpClient() as cdp:
            account = await get_or_create_wallet(cdp)
            return account.address

    return asyncio.run(fetch())


_WALLET_ADDRESS = _resolve_wallet_address()


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "runs": fetch_runs(),
            "spent_today": AuditLog().spent_today_usd(),
            "policy": SpendingPolicy.from_env(),
            "wallet_address": _WALLET_ADDRESS,
        },
    )


@app.get("/runs/{run_id}", response_class=HTMLResponse)
def run_detail(request: Request, run_id: str):
    run = fetch_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return templates.TemplateResponse(
        request, "run.html", {"run": run, "events": fetch_events(run_id)}
    )
