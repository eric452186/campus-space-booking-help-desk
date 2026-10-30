"""Fill the official midterm DOCX template with tested project evidence."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "Midterm-Report-Template-EN.docx"
EXPECTED_TEMPLATE_SHA256 = (
    "6e3d9d4923e5575030045f1a894cf65d3062276082e5c59c29a49ce510f42518"
)
SCREENSHOTS = ROOT / "report" / "screenshots"


def replace_paragraph(paragraph, text: str, *, bold: bool = False) -> None:
    paragraph.clear()
    run = paragraph.add_run(text)
    run.bold = bold


def fill_cell(cell, text: str, *, size: float = 10.5) -> None:
    paragraph = cell.paragraphs[0]
    paragraph.clear()
    run = paragraph.add_run(text)
    run.font.name = "Calibri"
    run.font.size = Pt(size)


def insert_screenshot(cell, path: Path, width: float) -> None:
    if not path.exists():
        raise FileNotFoundError(path)
    paragraph = cell.paragraphs[0]
    paragraph.clear()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    paragraph.add_run().add_picture(str(path), width=Inches(width))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--student-id", default="STUDENT_ID")
    parser.add_argument("--student-name", default="STUDENT_NAME")
    parser.add_argument("--github-url", default="GITHUB_URL")
    parser.add_argument("--hours", default="TBD_HOURS")
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "report" / "STUDENT_ID_STUDENT_NAME_Midterm.docx",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    actual_hash = hashlib.sha256(TEMPLATE.read_bytes()).hexdigest()
    if actual_hash != EXPECTED_TEMPLATE_SHA256:
        raise RuntimeError("The retained report template changed; distill it again first.")

    document = Document(TEMPLATE)
    paragraphs = document.paragraphs
    tables = document.tables

    replace_paragraph(
        paragraphs[0], "Midterm Project Report: Campus Space Booking Help Desk"
    )
    replace_paragraph(
        paragraphs[1],
        "This report presents a tested campus help desk that uses tool calling for "
        "changing booking data and RAG for written space-use rules. All records and "
        "policies are synthetic course demonstration data.",
    )

    basic = tables[0]
    for row, value in {
        1: args.student_id,
        2: args.student_name,
        3: "Campus Space Booking Help Desk",
        4: "☑ Tool calling   ☑ RAG",
        5: "gpt-4.1-mini; text-embedding-3-small for RAG",
        6: "Gradio web interface",
        7: args.github_url,
        8: "Not included (optional)",
    }.items():
        fill_cell(basic.cell(row, 1), value)

    replace_paragraph(
        paragraphs[5],
        "Scope: the app only supports campus space availability, bookings, "
        "cancellations, booking lookup, and space-use rules.",
    )
    replace_paragraph(
        paragraphs[6],
        "Rules: use tools before stating changing facts; retrieve rule text before "
        "answering policy questions; require complete booking details; never invent "
        "a missing record; refuse unrelated requests and hidden-prompt requests.",
    )

    topic = tables[1]
    topic_values = {
        1: (
            "A campus space booking help desk that answers rule questions and helps "
            "users find, create, check, and cancel room bookings."
        ),
        2: (
            "Students use the web app before a club meeting, group study session, or "
            "small campus event to check rules and arrange a room."
        ),
        3: (
            "Students who need a classroom or meeting room; campus service staff can "
            "also inspect the synthetic demonstration bookings."
        ),
        4: (
            "Accurate availability, booking and cancellation actions, booking-status "
            "lookup, and sourced answers about hours, food, equipment, and safety."
        ),
        5: (
            "A general AI cannot read or update the current SQLite records and does not "
            "know these project-specific campus rules, so it could invent facts."
        ),
    }
    for row, value in topic_values.items():
        fill_cell(topic.cell(row, 1), value, size=10.0)

    replace_paragraph(
        paragraphs[8],
        "The implementation separates changing structured facts from long written "
        "rules so each source is handled by the correct technique.",
    )
    parts = tables[2]
    part_values = {
        1: (
            "☑ Reads data from a database or a data file",
            "SQLite tools read room capacity, availability, and booking status; the RAG "
            "component reads the synthetic campus-rules document.",
        ),
        2: (
            "☑ Writes data into a database (orders, bookings, messages…)",
            "create_booking inserts a confirmed SQLite row; cancel_booking updates the "
            "matching record only after the tool verifies it exists.",
        ),
        3: (
            "☑ An agent that calls tools",
            "The model selects availability, create, lookup, cancel, or rule-search "
            "tools; Python executes them and returns structured results.",
        ),
        4: (
            "☑ RAG: searches long text documents",
            "Rule sections are embedded with text-embedding-3-small; cosine search "
            "retrieves the most relevant evidence before the answer is written.",
        ),
        5: (
            "☑ Handles user requests (ordering, booking, asking for help…)",
            "Users can ask rules, find a suitable room, create a booking, check its "
            "saved state, and cancel an existing booking through chat.",
        ),
        6: (
            "☑ Something else",
            "The Gradio interface keeps conversation context, shows examples, resets "
            "synthetic data, and clearly states its safety boundary.",
        ),
    }
    for row, (label, explanation) in part_values.items():
        fill_cell(parts.cell(row, 0), label, size=10.0)
        fill_cell(parts.cell(row, 1), explanation, size=9.8)

    replace_paragraph(
        paragraphs[11],
        "The following screenshots are from live OpenAI API conversations on "
        "October 30, 2026. Each answer was checked against the retrieved rule or the "
        "saved SQLite record.",
    )

    paragraphs[12].paragraph_format.page_break_before = True
    replace_paragraph(paragraphs[12], "Conversation 1: Food Rule Retrieved with RAG")
    replace_paragraph(paragraphs[13], "What the user wanted and why the answer is correct:")
    replace_paragraph(
        paragraphs[14],
        "The user asked whether a boxed meal is allowed in a library discussion room. "
        "The app retrieved the Food and Cleaning section and correctly stated that "
        "only covered drinks are allowed and meals are prohibited, with the source named.",
    )
    insert_screenshot(
        tables[3].cell(0, 0),
        SCREENSHOTS / "conversation_1_rag_report.png",
        5.9,
    )

    paragraphs[16].paragraph_format.page_break_before = True
    replace_paragraph(
        paragraphs[16], "Conversation 2: Availability Check and Confirmed Booking"
    )
    replace_paragraph(paragraphs[17], "What the user wanted and why the answer is correct:")
    replace_paragraph(
        paragraphs[18],
        "The user requested a room for 12 people, then explicitly booked ENG-A101. "
        "The availability tool returned two valid rooms and create_booking wrote "
        "BK0001 with the requested date, time, room, and purpose.",
    )
    insert_screenshot(
        tables[4].cell(0, 0),
        SCREENSHOTS / "conversation_2_booking_report.png",
        5.2,
    )

    paragraphs[20].paragraph_format.page_break_before = True
    replace_paragraph(
        paragraphs[20], "Conversation 3: Missing Booking Is Not Invented"
    )
    replace_paragraph(
        paragraphs[21],
        "The user asked for B9999, which does not exist. The lookup tool returned "
        "found=false and the app used its exact not-found response instead of inventing "
        "a room, owner, date, or status.",
    )
    replace_paragraph(paragraphs[22], "This test started in a fresh conversation.")
    insert_screenshot(
        tables[5].cell(0, 0),
        SCREENSHOTS / "conversation_3_missing_report.png",
        5.9,
    )

    paragraphs[24].paragraph_format.page_break_before = True
    replace_paragraph(paragraphs[24], "Saved Data Evidence: BK0001 Read Back from SQLite")
    replace_paragraph(
        paragraphs[25],
        "After the create tool returned BK0001, a separate lookup read the same row "
        "from SQLite. Room ENG-A101, 2026-11-06, 14:00-16:00, purpose, and confirmed "
        "status all match the booking response.",
    )
    replace_paragraph(paragraphs[26], "")
    insert_screenshot(
        tables[6].cell(0, 0),
        SCREENSHOTS / "saved_data_evidence_report.png",
        5.05,
    )

    paragraphs[27].paragraph_format.page_break_before = True
    ai_table = tables[7]
    for row, value in {
        1: "Codex",
        2: "☑ In a console / coding-agent environment\n☐ Inside VS Code\n☐ In a web chat page\n☐ Other tools",
        3: f"About {args.hours} hours",
        4: (
            "Planning, code generation and review, synthetic data, system prompt, "
            "automated tests, live debugging, UI screenshots, README, and report."
        ),
    }.items():
        fill_cell(ai_table.cell(row, 1), value, size=10.0)

    replace_paragraph(
        paragraphs[29],
        "The main design problem was preventing the model from mixing changing booking "
        "facts with written rules. I separated the sources: SQLite tools handle room "
        "availability and booking actions, while RAG retrieves only relevant rule sections. "
        "Structured tool results and exact refusal sentences prevent unsupported success claims.",
    )
    replace_paragraph(
        paragraphs[30],
        "Codex helped most with modularizing the tool loop, tests, interface, and report. "
        "Its output still required verification: the first UI used Gradio parameters that "
        "changed in version 6, so I inspected the installed API, fixed the component arguments, "
        "and reran unit, import, live API, database, and screenshot checks.",
    )

    replace_paragraph(paragraphs[32], "Final submission verification:")
    replace_paragraph(
        paragraphs[33],
        f"☐ My PDF is named \"{args.student_id}_{args.student_name}_Midterm.pdf\" and is uploaded to the course site.",
    )
    replace_paragraph(paragraphs[34], "☑ My app uses both tool calling and RAG.")
    replace_paragraph(
        paragraphs[35],
        "☐ My GitHub repository is public, its link is in Basic Information, and the link opens in a private window.",
    )
    replace_paragraph(
        paragraphs[36],
        "☑ The package contains code, synthetic data, .env.example, requirements, README.md, and .gitignore, but no .env, .env.local, or API key.",
    )
    replace_paragraph(
        paragraphs[37],
        "☑ All room, booking, and campus-rule data is synthetic course demonstration data.",
    )

    args.output = args.output.resolve()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    document.save(args.output)
    print(args.output)


if __name__ == "__main__":
    main()
