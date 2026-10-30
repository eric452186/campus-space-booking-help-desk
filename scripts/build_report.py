"""Fill only the official midterm template's designated answer slots."""

from __future__ import annotations

import argparse
import hashlib
from copy import deepcopy
from io import BytesIO
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Inches, Pt
from docx.text.run import Run
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "Midterm-Report-Template-EN.docx"
EXPECTED_TEMPLATE_SHA256 = (
    "6e3d9d4923e5575030045f1a894cf65d3062276082e5c59c29a49ce510f42518"
)
SCREENSHOTS = ROOT / "report" / "screenshots"
NAME_FONT_PATH = Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf")

ANSWER_PARAGRAPHS = (14, 18, 22, 26, 30)
CHECKLIST_PARAGRAPHS = (33, 34, 35, 36, 37)
CHECKED_CHECKLIST_PARAGRAPHS = (34, 35, 36, 37)
EDITABLE_PARAGRAPHS = (12, 16) + ANSWER_PARAGRAPHS + CHECKLIST_PARAGRAPHS
FIXED_PARAGRAPHS = tuple(
    index for index in range(38) if index not in set(EDITABLE_PARAGRAPHS)
)


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


def fill_name_cell(cell, text: str) -> None:
    """Render the Chinese name visibly while retaining its searchable text."""

    if not NAME_FONT_PATH.exists():
        raise FileNotFoundError(NAME_FONT_PATH)

    font = ImageFont.truetype(str(NAME_FONT_PATH), 48)
    left, top, right, bottom = font.getbbox(text)
    padding = 6
    image = Image.new(
        "RGBA",
        (right - left + 2 * padding, bottom - top + 2 * padding),
        (255, 255, 255, 0),
    )
    draw = ImageDraw.Draw(image)
    draw.text((padding - left, padding - top), text, font=font, fill=(0, 0, 0, 255))

    stream = BytesIO()
    image.save(stream, format="PNG", dpi=(300, 300))
    stream.seek(0)

    paragraph = cell.paragraphs[0]
    paragraph.clear()
    picture = paragraph.add_run().add_picture(stream, height=Inches(0.18))
    picture._inline.docPr.set("descr", text)
    picture._inline.docPr.set("title", text)

    searchable = paragraph.add_run(text)
    searchable.font.hidden = True
    searchable.font.size = Pt(1)


def tick_first_checkbox(paragraph) -> None:
    """Change one checkbox glyph while preserving all surrounding wording."""

    if not paragraph.text.startswith("☐"):
        raise RuntimeError(f"Expected an unchecked item, found: {paragraph.text!r}")
    for run in paragraph.runs:
        if "☐" in run.text:
            run.text = run.text.replace("☐", "☑", 1)
            return
    raise RuntimeError("The checkbox was not found in a text run.")


def tick_styled_checkboxes(
    paragraph, *, checked_positions: set[int], expected_count: int
) -> None:
    """Tick selected boxes while preserving every surrounding styled text segment."""

    box_index = 0
    for original_run in list(paragraph.runs):
        if "☐" not in original_run.text:
            continue

        pieces = original_run.text.split("☐")
        for piece_index, piece in enumerate(pieces):
            if piece:
                text_element = deepcopy(original_run._r)
                text_run = Run(text_element, paragraph)
                text_run.text = piece
                original_run._r.addprevious(text_element)

            if piece_index == len(pieces) - 1:
                continue

            box_element = deepcopy(original_run._r)
            box_run = Run(box_element, paragraph)
            if box_index in checked_positions:
                box_run.text = "☑"
                box_run.font.name = "Calibri"
                box_run.font.italic = False
                box_run._element.rPr.rFonts.set(qn("w:ascii"), "Calibri")
                box_run._element.rPr.rFonts.set(qn("w:hAnsi"), "Calibri")
            else:
                box_run.text = "☐"
            original_run._r.addprevious(box_element)
            box_index += 1

        original_run._r.getparent().remove(original_run._r)

    if box_index != expected_count:
        raise RuntimeError(
            f"Expected {expected_count} unchecked boxes, found {box_index}: {paragraph.text!r}"
        )
    if not checked_positions.issubset(set(range(box_index))):
        raise RuntimeError("A requested checkbox position does not exist.")


def insert_screenshot(
    cell, path: Path, width: float, expected: str, alt_text: str
) -> None:
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
    picture = paragraph.add_run().add_picture(str(path), width=Inches(width))
    picture._inline.docPr.set("descr", alt_text)
    picture._inline.docPr.set("title", alt_text)


def _without_checkbox(text: str) -> str:
    if not text or text[0] not in {"☐", "☑"}:
        raise RuntimeError(f"Expected checkbox text, found: {text!r}")
    return text[1:]


def _normalize_checkboxes(text: str) -> str:
    return text.replace("☑", "☐")


def verify_template_text(
    template_path: Path, output_path: Path, args: argparse.Namespace
) -> None:
    """Fail if any fixed template wording changed outside approved answer slots."""

    reference = Document(template_path)
    result = Document(output_path)

    if len(reference.paragraphs) != len(result.paragraphs):
        raise RuntimeError("Paragraph count changed from the retained template.")
    if len(reference.tables) != len(result.tables):
        raise RuntimeError("Table count changed from the retained template.")

    for index in FIXED_PARAGRAPHS:
        if result.paragraphs[index].text != reference.paragraphs[index].text:
            raise RuntimeError(f"Fixed template paragraph P{index} changed.")
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

    source_basic = reference.tables[0]
    result_basic = result.tables[0]
    for row, provided in {
        1: args.student_id,
        2: args.student_name,
        7: args.github_url,
        8: args.demo_video,
    }.items():
        if provided.strip() and result_basic.cell(row, 1).text != provided:
            raise RuntimeError(f"Basic Information row {row} has the wrong answer.")
        if not provided.strip() and result_basic.cell(row, 1).text != source_basic.cell(row, 1).text:
            raise RuntimeError(f"Unanswered Basic Information row {row} changed.")
    if _normalize_checkboxes(result_basic.cell(4, 1).text) != _normalize_checkboxes(
        source_basic.cell(4, 1).text
    ):
        raise RuntimeError("Technique option wording changed beyond its checkboxes.")
    if result_basic.cell(4, 1).text.count("☑") != 2:
        raise RuntimeError("Both technique checkboxes must be checked.")

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
    if _normalize_checkboxes(ai_location_result) != _normalize_checkboxes(ai_location_source):
        raise RuntimeError("AI-tool location option wording changed.")
    if not ai_location_result.startswith("☑") or ai_location_result.count("☑") != 1:
        raise RuntimeError("Only the console AI-tool location may be checked.")
    if not args.hours.strip() and reference.tables[7].cell(3, 1).text != result.tables[7].cell(3, 1).text:
        raise RuntimeError("The unanswered AI-hours hint changed.")

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
    parser.add_argument("--template", type=Path, default=TEMPLATE)
    parser.add_argument("--student-id", default="")
    parser.add_argument("--student-name", default="")
    parser.add_argument("--github-url", default="")
    parser.add_argument("--demo-video", default="")
    parser.add_argument("--hours", default="")
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "report" / "STUDENT_ID_STUDENT_NAME_Midterm.docx",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    template_path = args.template.resolve()
    actual_hash = hashlib.sha256(template_path.read_bytes()).hexdigest()
    if actual_hash != EXPECTED_TEMPLATE_SHA256:
        raise RuntimeError("The retained report template changed; distill it again first.")

    document = Document(template_path)
    paragraphs = document.paragraphs
    tables = document.tables

    basic = tables[0]
    basic_values = {
        3: "Campus Space Booking Help Desk",
        5: "gpt-4.1-mini; text-embedding-3-small for RAG",
        6: "Gradio",
    }
    if args.student_id.strip():
        basic_values[1] = args.student_id
    if args.student_name.strip():
        basic_values[2] = args.student_name
    if args.github_url.strip():
        basic_values[7] = args.github_url
    if args.demo_video.strip():
        basic_values[8] = args.demo_video
    for row, value in basic_values.items():
        if row == 2:
            fill_name_cell(basic.cell(row, 1), value)
        else:
            fill_answer_cell(basic.cell(row, 1), value)
    tick_styled_checkboxes(
        basic.cell(4, 1).paragraphs[0],
        checked_positions={0, 1},
        expected_count=2,
    )

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
        "Conversation 1: food-rule RAG answer with its cited rule section.",
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
        "Conversation 2: room search and confirmed booking BK0001.",
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
        "Conversation 3: honest not-found response for booking B9999.",
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
        "Saved-data evidence: lookup confirms stored booking BK0001.",
    )

    ai_table = tables[7]
    fill_answer_cell(ai_table.cell(1, 1), "Codex")
    tick_styled_checkboxes(
        ai_table.cell(2, 1).paragraphs[0],
        checked_positions={0},
        expected_count=4,
    )
    if args.hours.strip():
        fill_answer_cell(ai_table.cell(3, 1), f"about {args.hours} hours")
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
    verify_template_text(template_path, output_path, args)

    if hashlib.sha256(template_path.read_bytes()).hexdigest() != actual_hash:
        raise RuntimeError("The retained report template was modified during authoring.")
    print(output_path)


if __name__ == "__main__":
    main()
