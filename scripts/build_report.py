"""Fill only the official midterm template's designated answer slots."""

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

HINT_PARAGRAPHS = (1, 5, 8, 11, 13, 17, 21, 25, 29, 32)
FIXED_PARAGRAPHS = (0, 2, 3, 4, 6, 7, 9, 10, 15, 19, 20, 23, 24, 27, 28, 31)
ANSWER_PARAGRAPHS = (14, 18, 22, 26, 30)
CHECKLIST_PARAGRAPHS = (33, 34, 35, 36, 37)
CHECKED_CHECKLIST_PARAGRAPHS = (34, 36, 37)


def clear_hint(paragraph) -> None:
    """Remove a template hint without inserting replacement prose."""

    paragraph.clear()


def fill_blank_paragraph(paragraph, text: str) -> None:
    """Fill an existing blank answer slot and refuse to overwrite template text."""

    if paragraph.text:
        raise RuntimeError(f"Expected a blank answer paragraph, found: {paragraph.text!r}")
    paragraph.add_run(text)


def replace_placeholder_paragraph(paragraph, expected: str, text: str) -> None:
    """Replace an explicit write-your-answer placeholder only."""

    if paragraph.text != expected:
        raise RuntimeError(
            f"Unexpected placeholder text: expected {expected!r}, found {paragraph.text!r}"
        )
    paragraph.clear()
    paragraph.add_run(text)


def fill_answer_cell(cell, text: str, *, size: float = 10.5) -> None:
    """Replace only the contents of a documented answer cell."""

    paragraph = cell.paragraphs[0]
    paragraph.clear()
    if not text:
        return
    run = paragraph.add_run(text)
    run.font.name = "Calibri"
    run.font.size = Pt(size)


def tick_first_checkbox(paragraph) -> None:
    """Change one checkbox glyph while preserving all surrounding wording."""

    if not paragraph.text.startswith("☐"):
        raise RuntimeError(f"Expected an unchecked item, found: {paragraph.text!r}")
    for run in paragraph.runs:
        if "☐" in run.text:
            run.text = run.text.replace("☐", "☑", 1)
            return
    raise RuntimeError("The checkbox was not found in a text run.")


def insert_screenshot(cell, path: Path, width: float, expected: str) -> None:
    """Replace one screenshot placeholder cell with its tested evidence image."""

    if not path.exists():
        raise FileNotFoundError(path)
    if cell.text != expected:
        raise RuntimeError(
            f"Unexpected screenshot placeholder: expected {expected!r}, found {cell.text!r}"
        )
    paragraph = cell.paragraphs[0]
    paragraph.clear()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    paragraph.add_run().add_picture(str(path), width=Inches(width))


def _without_checkbox(text: str) -> str:
    if not text or text[0] not in {"☐", "☑"}:
        raise RuntimeError(f"Expected checkbox text, found: {text!r}")
    return text[1:]


def verify_template_text(output_path: Path) -> None:
    """Fail if any fixed template wording changed outside approved answer slots."""

    reference = Document(TEMPLATE)
    result = Document(output_path)

    if len(reference.paragraphs) != len(result.paragraphs):
        raise RuntimeError("Paragraph count changed from the retained template.")
    if len(reference.tables) != len(result.tables):
        raise RuntimeError("Table count changed from the retained template.")

    for index in FIXED_PARAGRAPHS:
        if result.paragraphs[index].text != reference.paragraphs[index].text:
            raise RuntimeError(f"Fixed template paragraph P{index} changed.")
    for index in HINT_PARAGRAPHS:
        if result.paragraphs[index].text:
            raise RuntimeError(f"Template hint P{index} was rewritten instead of cleared.")
    for index in ANSWER_PARAGRAPHS:
        if not result.paragraphs[index].text.strip():
            raise RuntimeError(f"Answer paragraph P{index} is empty.")

    for table_index in (0, 1, 7):
        source_table = reference.tables[table_index]
        result_table = result.tables[table_index]
        for column in range(len(source_table.columns)):
            if result_table.cell(0, column).text != source_table.cell(0, column).text:
                raise RuntimeError(f"Table {table_index} header text changed.")
        for row in range(1, len(source_table.rows)):
            if result_table.cell(row, 0).text != source_table.cell(row, 0).text:
                raise RuntimeError(f"Table {table_index} question row {row} changed.")

    source_parts = reference.tables[2]
    result_parts = result.tables[2]
    for column in range(2):
        if result_parts.cell(0, column).text != source_parts.cell(0, column).text:
            raise RuntimeError("Part 2 table header text changed.")
    for row in range(1, len(source_parts.rows)):
        if _without_checkbox(result_parts.cell(row, 0).text) != _without_checkbox(
            source_parts.cell(row, 0).text
        ):
            raise RuntimeError(f"Part 2 label row {row} changed beyond its checkbox.")
        if not result_parts.cell(row, 0).text.startswith("☑"):
            raise RuntimeError(f"Part 2 row {row} was not checked.")

    ai_location_source = reference.tables[7].cell(2, 1).text
    ai_location_result = result.tables[7].cell(2, 1).text
    if _without_checkbox(ai_location_result) != _without_checkbox(ai_location_source):
        raise RuntimeError("AI-tool location option wording changed.")

    for index in CHECKLIST_PARAGRAPHS:
        source = reference.paragraphs[index].text
        final = result.paragraphs[index].text
        if _without_checkbox(final) != _without_checkbox(source):
            raise RuntimeError(f"Checklist sentence P{index} changed.")
        expected_mark = "☑" if index in CHECKED_CHECKLIST_PARAGRAPHS else "☐"
        if not final.startswith(expected_mark):
            raise RuntimeError(f"Checklist checkbox P{index} has the wrong state.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--student-id", default="")
    parser.add_argument("--student-name", default="")
    parser.add_argument("--github-url", default="")
    parser.add_argument("--hours", default="")
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

    for index in HINT_PARAGRAPHS:
        clear_hint(paragraphs[index])

    basic = tables[0]
    for row, value in {
        1: args.student_id,
        2: args.student_name,
        3: "Campus Space Booking Help Desk",
        4: "☑ Tool calling   ☑ RAG",
        5: "gpt-4.1-mini; text-embedding-3-small for RAG",
        6: "Gradio",
        7: args.github_url,
        8: "",
    }.items():
        fill_answer_cell(basic.cell(row, 1), value)

    topic = tables[1]
    topic_values = {
        1: (
            "A campus space booking help desk for finding rooms, managing bookings, "
            "and answering space-use questions. It uses tools for booking facts, RAG "
            "for rules, requires complete details, never invents missing records, and "
            "refuses unrelated requests."
        ),
        2: (
            "Students use it before club meetings, group study, or campus events to "
            "check rules and arrange a room."
        ),
        3: (
            "Students needing a classroom or meeting room; service staff can inspect "
            "the synthetic bookings."
        ),
        4: (
            "Accurate availability, booking actions, status lookup, and sourced "
            "answers about hours, food, equipment, and safety."
        ),
        5: (
            "A general AI cannot access the project SQLite records or campus rules, "
            "so it cannot verify or save a booking."
        ),
    }
    for row, value in topic_values.items():
        fill_answer_cell(topic.cell(row, 1), value, size=10.0)

    parts = tables[2]
    part_values = {
        1: (
            "SQLite tools read room capacity, availability, and booking status; the "
            "RAG component reads the synthetic campus-rules document."
        ),
        2: (
            "create_booking inserts a confirmed SQLite row; cancel_booking updates "
            "the matching record only after the tool verifies it exists."
        ),
        3: (
            "The model selects availability, create, lookup, cancel, or rule-search "
            "tools; Python executes them and returns structured results."
        ),
        4: (
            "Rule sections are embedded with text-embedding-3-small; cosine search "
            "retrieves the most relevant evidence before the answer is written."
        ),
        5: (
            "Users can ask rules, find a suitable room, create a booking, check its "
            "saved state, and cancel an existing booking through chat."
        ),
        6: (
            "The Gradio interface keeps conversation context, shows examples, resets "
            "synthetic data, and clearly states its safety boundary."
        ),
    }
    for row, explanation in part_values.items():
        tick_first_checkbox(parts.cell(row, 0).paragraphs[0])
        fill_answer_cell(parts.cell(row, 1), explanation, size=9.8)

    for index in (10, 16, 20, 24, 27):
        paragraphs[index].paragraph_format.page_break_before = True

    replace_placeholder_paragraph(
        paragraphs[12],
        'Conversation 1: (Write What the User Wants, Such as "Booking a Room for Two Nights")',
        "Conversation 1: Asking About the Food Rule",
    )
    fill_blank_paragraph(
        paragraphs[14],
        "The user asked whether a boxed meal is allowed in a library discussion room. "
        "The app retrieved the Food and Cleaning section and correctly stated that "
        "only covered drinks are allowed and meals are prohibited, with the source named.",
    )
    insert_screenshot(
        tables[3].cell(0, 0),
        SCREENSHOTS / "conversation_1_rag_report.png",
        5.9,
        "(Paste your screenshot here: Conversation 1)",
    )

    replace_placeholder_paragraph(
        paragraphs[16],
        'Conversation 2: (Write What the User Wants, Such as "Booking a Room for Two Nights")',
        "Conversation 2: Finding a Room and Creating a Booking",
    )
    fill_blank_paragraph(
        paragraphs[18],
        "The user requested a room for 12 people, then explicitly booked ENG-A101. "
        "The availability tool returned two valid rooms and create_booking wrote "
        "BK0001 with the requested date, time, room, and purpose.",
    )
    insert_screenshot(
        tables[4].cell(0, 0),
        SCREENSHOTS / "conversation_2_booking_report.png",
        5.2,
        "(Paste your screenshot here: Conversation 2)",
    )

    fill_blank_paragraph(
        paragraphs[22],
        "The user asked for booking B9999, which does not exist. The lookup tool "
        "returned found=false, and the app answered that it could not find the record "
        "instead of inventing a room, owner, date, or status.",
    )
    insert_screenshot(
        tables[5].cell(0, 0),
        SCREENSHOTS / "conversation_3_missing_report.png",
        5.9,
        "(Paste your screenshot here: Conversation 3)",
    )

    fill_blank_paragraph(
        paragraphs[26],
        "After create_booking returned BK0001, a separate lookup read the same row "
        "from SQLite. Room ENG-A101, 2026-11-06, 14:00-16:00, purpose, and confirmed "
        "status all match the booking response.",
    )
    insert_screenshot(
        tables[6].cell(0, 0),
        SCREENSHOTS / "saved_data_evidence_report.png",
        4.85,
        "(Paste your screenshot here: the saved data)",
    )

    ai_table = tables[7]
    fill_answer_cell(ai_table.cell(1, 1), "Codex")
    fill_answer_cell(
        ai_table.cell(2, 1),
        "☑ In a console (a command-line tool)\n"
        "☐ Inside VS Code\n"
        "☐ In a web chat page\n"
        "☐ Other tools: ____",
        size=10.0,
    )
    fill_answer_cell(
        ai_table.cell(3, 1),
        f"about {args.hours} hours" if args.hours.strip() else "",
    )
    fill_answer_cell(
        ai_table.cell(4, 1),
        "Planning, code generation and review, synthetic data, system prompt, "
        "automated tests, live debugging, UI screenshots, README, and report.",
        size=10.0,
    )

    fill_blank_paragraph(
        paragraphs[30],
        "The main problem was keeping changing booking facts separate from written "
        "rules. I used SQLite tools for bookings and RAG for rule sections, then "
        "verified each answer against tool results. Codex helped with the tool loop, "
        "tests, interface, and report, but its first Gradio code used changed version-6 "
        "parameters; I checked the installed API, corrected them, and reran all tests.",
    )

    for index in CHECKED_CHECKLIST_PARAGRAPHS:
        tick_first_checkbox(paragraphs[index])

    output_path = args.output.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    document.save(output_path)
    verify_template_text(output_path)

    if hashlib.sha256(TEMPLATE.read_bytes()).hexdigest() != actual_hash:
        raise RuntimeError("The retained report template was modified during authoring.")
    print(output_path)


if __name__ == "__main__":
    main()
