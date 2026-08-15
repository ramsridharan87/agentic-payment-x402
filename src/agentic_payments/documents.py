from datetime import datetime, timezone
from pathlib import Path

from fpdf import FPDF

from .audit import data_dir


def output_dir() -> Path:
    path = data_dir() / "outputs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def pdf_path(run_id: str) -> Path:
    return output_dir() / f"{run_id}.pdf"


def _latin1(text: str) -> str:
    # Core PDF fonts are Latin-1 only; swap anything else out rather than
    # crashing on smart quotes/em-dashes/emoji the model likes to produce.
    return text.encode("latin-1", "replace").decode("latin-1")


def generate_pdf(run_id: str, goal: str, answer: str) -> Path:
    """Render the agent's final answer as a downloadable PDF."""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_margins(20, 20, 20)

    pdf.set_font("helvetica", "B", 16)
    pdf.multi_cell(0, 10, _latin1(goal))
    pdf.ln(2)

    pdf.set_font("helvetica", "", 9)
    pdf.set_text_color(120, 120, 120)
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    pdf.multi_cell(0, 6, f"Generated {timestamp} by agentic-payments")
    pdf.ln(6)

    pdf.set_font("helvetica", "", 11)
    pdf.set_text_color(0, 0, 0)
    pdf.multi_cell(0, 7, _latin1(answer))

    path = pdf_path(run_id)
    pdf.output(str(path))
    return path
