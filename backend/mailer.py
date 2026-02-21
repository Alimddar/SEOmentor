"""Email delivery and branded PDF generation for SEO plans."""

from datetime import datetime
from email.message import EmailMessage
from email.utils import formataddr
import os
from pathlib import Path
import smtplib
import ssl
import textwrap

from dotenv import load_dotenv

from models import AIAnalysisResult

load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env")

PAGE_WIDTH = 612
PAGE_HEIGHT = 792


def _escape_pdf_text(value: str) -> str:
    safe = value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    return safe.encode("latin-1", "replace").decode("latin-1")


def _build_pdf(page_streams: list[bytes]) -> bytes:
    objects: dict[int, bytes] = {}
    objects[1] = b"<< /Type /Catalog /Pages 2 0 R >>"
    objects[3] = b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"
    objects[4] = b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>"

    page_refs: list[str] = []
    for idx, stream in enumerate(page_streams):
        page_obj_num = 5 + idx * 2
        content_obj_num = page_obj_num + 1
        objects[page_obj_num] = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {PAGE_WIDTH} {PAGE_HEIGHT}] "
            f"/Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> "
            f"/Contents {content_obj_num} 0 R >>"
        ).encode("latin-1")
        objects[content_obj_num] = (
            f"<< /Length {len(stream)} >>\nstream\n".encode("latin-1")
            + stream
            + b"\nendstream"
        )
        page_refs.append(f"{page_obj_num} 0 R")

    objects[2] = f"<< /Type /Pages /Kids [{' '.join(page_refs)}] /Count {len(page_refs)} >>".encode(
        "latin-1"
    )

    header = b"%PDF-1.4\n"
    body = bytearray(header)
    offsets: dict[int, int] = {}
    for obj_num in sorted(objects):
        offsets[obj_num] = len(body)
        body.extend(f"{obj_num} 0 obj\n".encode("latin-1"))
        body.extend(objects[obj_num])
        body.extend(b"\nendobj\n")

    xref_start = len(body)
    max_obj = max(objects)
    body.extend(f"xref\n0 {max_obj + 1}\n".encode("latin-1"))
    body.extend(b"0000000000 65535 f \n")
    for obj_num in range(1, max_obj + 1):
        body.extend(f"{offsets[obj_num]:010d} 00000 n \n".encode("latin-1"))

    body.extend(f"trailer\n<< /Size {max_obj + 1} /Root 1 0 R >>\n".encode("latin-1"))
    body.extend(f"startxref\n{xref_start}\n%%EOF\n".encode("latin-1"))
    return bytes(body)


def _build_cover_stream(*, project_id: int, url: str, score: float, plan_days: int, created_at: str) -> bytes:
    commands = [
        "q",
        "0.06 0.62 0.34 rg",
        f"0 {PAGE_HEIGHT - 86} {PAGE_WIDTH} 86 re f",
        "Q",
        "BT",
        "/F2 30 Tf",
        "1 1 1 rg",
        "42 742 Td",
        "(SEOmentor) Tj",
        "ET",
        "BT",
        "/F1 12 Tf",
        "1 1 1 rg",
        "42 720 Td",
        "(Your AI SEO Co-Founder) Tj",
        "ET",
        "BT",
        "/F2 24 Tf",
        "0.05 0.32 0.18 rg",
        "42 650 Td",
        "(AI SEO Roadmap Report) Tj",
        "ET",
        "BT",
        "/F1 12 Tf",
        "0.14 0.30 0.23 rg",
        "42 620 Td",
        f"(Project ID: {project_id}) Tj",
        "ET",
        "BT",
        "/F1 12 Tf",
        "0.14 0.30 0.23 rg",
        "42 598 Td",
        f"(Website: {_escape_pdf_text(url)}) Tj",
        "ET",
        "BT",
        "/F1 12 Tf",
        "0.14 0.30 0.23 rg",
        "42 576 Td",
        f"(Generated: {_escape_pdf_text(created_at)}) Tj",
        "ET",
        "BT",
        "/F2 18 Tf",
        "0.05 0.50 0.26 rg",
        "42 520 Td",
        f"(SEO Score: {int(round(score))}/100) Tj",
        "ET",
        "BT",
        "/F2 14 Tf",
        "0.08 0.44 0.24 rg",
        "42 492 Td",
        f"({plan_days}-Day Execution Plan) Tj",
        "ET",
    ]
    return "\n".join(commands).encode("latin-1", "replace")


def _build_detail_page_stream(
    *, lines: list[str], project_id: int, page_number: int, total_pages: int
) -> bytes:
    commands = [
        "q",
        "0.91 0.98 0.94 rg",
        "30 748 552 26 re f",
        "Q",
        "BT",
        "/F2 12 Tf",
        "0.05 0.35 0.19 rg",
        "40 758 Td",
        f"(SEOmentor Report - Project #{project_id}) Tj",
        "ET",
        "BT",
        "/F1 10 Tf",
        "0 0 0 rg",
        "40 730 Td",
        "14 TL",
    ]
    for line in lines:
        commands.append(f"({_escape_pdf_text(line)}) Tj")
        commands.append("T*")
    commands.extend(
        [
            "ET",
            "BT",
            "/F1 9 Tf",
            "0.45 0.45 0.45 rg",
            "500 18 Td",
            f"(Page {page_number} of {total_pages}) Tj",
            "ET",
        ]
    )
    return "\n".join(commands).encode("latin-1", "replace")


def _wrap_lines(values: list[str], max_chars: int = 88) -> list[str]:
    out: list[str] = []
    for value in values:
        if not value:
            out.append("")
            continue
        wrapped = textwrap.wrap(value, width=max_chars) or [value]
        out.extend(wrapped)
    return out


def build_plan_pdf(
    *,
    project_id: int,
    url: str,
    result: AIAnalysisResult,
    plan_days: int,
) -> bytes:
    roadmap_by_day: dict[int, str] = {}
    for row in result.get("roadmap", []):
        if not isinstance(row, dict):
            continue
        day = row.get("day")
        task = row.get("task")
        try:
            day_num = int(day)
        except (TypeError, ValueError):
            continue
        if 1 <= day_num <= plan_days and isinstance(task, str) and task.strip():
            roadmap_by_day[day_num] = task.strip()

    created = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    score = float(result.get("seo_score", 0))

    detail_lines = [
        "Summary",
        f"Website: {url}",
        f"SEO Score: {score:.0f}/100",
        "",
        "Key Issues",
    ]
    for idx, issue in enumerate(result.get("issues", []), start=1):
        detail_lines.append(f"{idx}. {issue}")

    detail_lines.extend(["", "Competitors"])
    for idx, competitor in enumerate(result.get("competitors", []), start=1):
        if isinstance(competitor, dict):
            name = str(competitor.get("name") or "").strip()
            reason = str(competitor.get("reason") or "").strip()
            detail_lines.append(f"{idx}. {name} - {reason}")

    detail_lines.extend(["", "Keyword Gaps"])
    for idx, gap in enumerate(result.get("keyword_gaps", []), start=1):
        detail_lines.append(f"{idx}. {gap}")

    detail_lines.extend(["", f"{plan_days}-Day Roadmap"])
    for day in range(1, plan_days + 1):
        detail_lines.append(f"Day {day}: {roadmap_by_day.get(day, 'No task assigned.')}")

    wrapped_lines = _wrap_lines(detail_lines)
    lines_per_page = 42
    chunks = [wrapped_lines[i : i + lines_per_page] for i in range(0, len(wrapped_lines), lines_per_page)]
    if not chunks:
        chunks = [["No data available."]]

    page_streams: list[bytes] = [
        _build_cover_stream(
            project_id=project_id,
            url=url,
            score=score,
            plan_days=plan_days,
            created_at=created,
        )
    ]
    total_pages = len(chunks) + 1
    for index, chunk in enumerate(chunks, start=2):
        page_streams.append(
            _build_detail_page_stream(
                lines=chunk,
                project_id=project_id,
                page_number=index,
                total_pages=total_pages,
            )
        )

    return _build_pdf(page_streams)


def send_plan_email(
    *,
    recipient_email: str,
    project_id: int,
    url: str,
    result: AIAnalysisResult,
    plan_days: int,
) -> bool:
    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "465"))
    smtp_username = os.getenv("SMTP_USERNAME", "").strip()
    smtp_password = os.getenv("SMTP_PASSWORD", "").strip()
    smtp_from_email = os.getenv("SMTP_FROM_EMAIL", smtp_username).strip()
    smtp_from_name = os.getenv("SMTP_FROM_NAME", "SEOmentor").strip() or "SEOmentor"

    missing_keys = []
    if not smtp_username:
        missing_keys.append("SMTP_USERNAME")
    if not smtp_password:
        missing_keys.append("SMTP_PASSWORD")
    if not smtp_from_email:
        missing_keys.append("SMTP_FROM_EMAIL")
    if missing_keys:
        print(f"EMAIL SKIPPED: Missing SMTP credentials: {', '.join(missing_keys)}")
        return False

    message = EmailMessage()
    message["Subject"] = f"Your SEOmentor {plan_days}-Day SEO Plan"
    message["From"] = formataddr((smtp_from_name, smtp_from_email))
    message["To"] = recipient_email
    message.set_content(
        "\n".join(
            [
                "Hi,",
                "",
                "Your SEOmentor roadmap is ready.",
                f"Project ID: {project_id}",
                f"Website: {url}",
                "",
                "The branded PDF report is attached.",
            ]
        )
    )

    pdf_bytes = build_plan_pdf(
        project_id=project_id,
        url=url,
        result=result,
        plan_days=plan_days,
    )
    message.add_attachment(
        pdf_bytes,
        maintype="application",
        subtype="pdf",
        filename=f"seomentor-plan-{project_id}.pdf",
    )

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(smtp_host, smtp_port, context=context, timeout=30) as smtp:
            smtp.login(smtp_username, smtp_password)
            smtp.send_message(message)
        print(f"EMAIL SENT: {recipient_email}")
        return True
    except Exception as e:
        print("EMAIL ERROR:", str(e))
        return False
