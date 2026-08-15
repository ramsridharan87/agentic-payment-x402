import asyncio
import threading
import uuid
from pathlib import Path

from cdp import CdpClient
from dotenv import load_dotenv
from fastapi import APIRouter, Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from ..agent.loop import run_agent
from ..audit import AuditLog, fetch_events, fetch_payment_events, fetch_run, fetch_runs
from ..documents import pdf_path
from ..guardrails import SpendingPolicy
from ..net import force_ipv4
from ..wallet.cdp_wallet import get_or_create_wallet
from .auth import require_auth

load_dotenv()
force_ipv4()

app = FastAPI(title="Agentic Payments - Decision Log")
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

# Everything except /healthz requires auth - this dashboard can trigger real
# payments, so an unauthenticated route is a deliberate, narrow exception
# (needed for Render's health check), not the default.
router = APIRouter(dependencies=[Depends(require_auth)])


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


def _resolve_wallet_address() -> str:
    async def fetch() -> str:
        async with CdpClient() as cdp:
            account = await get_or_create_wallet(cdp)
            return account.address

    return asyncio.run(fetch())


_WALLET_ADDRESS = _resolve_wallet_address()


@router.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "runs": fetch_runs(),
            "spent_today": AuditLog().spent_today_usd(),
            "spent_all_time": AuditLog().spent_all_time_usd(),
            "policy": SpendingPolicy.from_env(),
            "wallet_address": _WALLET_ADDRESS,
        },
    )


@router.get("/new", response_class=HTMLResponse)
def new_run_form(request: Request):
    return templates.TemplateResponse(request, "new_run.html", {})


@router.post("/runs")
def create_run(goal: str = Form(...)):
    run_id = str(uuid.uuid4())
    thread = threading.Thread(target=run_agent, args=(goal,), kwargs={"run_id": run_id}, daemon=True)
    thread.start()
    return RedirectResponse(url=f"/runs/{run_id}", status_code=303)


@router.get("/runs/{run_id}", response_class=HTMLResponse)
def run_detail(request: Request, run_id: str):
    run = fetch_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return templates.TemplateResponse(
        request,
        "run.html",
        {
            "run": run,
            "events": fetch_events(run_id),
            "has_pdf": pdf_path(run_id).exists(),
        },
    )


@router.get("/runs/{run_id}/download")
def download_run(run_id: str):
    path = pdf_path(run_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="No document for this run")
    return FileResponse(path, media_type="application/pdf", filename=f"{run_id}.pdf")


@router.get("/purchases", response_class=HTMLResponse)
def purchases(request: Request):
    return templates.TemplateResponse(
        request,
        "purchases.html",
        {
            "events": fetch_payment_events(),
            "spent_today": AuditLog().spent_today_usd(),
            "spent_all_time": AuditLog().spent_all_time_usd(),
            "policy": SpendingPolicy.from_env(),
        },
    )


app.include_router(router)
