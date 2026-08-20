# SPDX-License-Identifier: GPL-3.0-or-later
"""Newspaper-style A4 PDF export for a completed crossword layout.

The renderer accepts only a :class:`Puzzle`. It deliberately has no Anki,
collection, browser, or UI-state dependency. Qt's PDF backend is used because
it is already shipped by Anki and can use installed Japanese-capable fonts.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
import re
from typing import Iterable

from ..crossword.puzzle import PlacedEntry, Puzzle
from ..vocabulary.text import anki_html_for_preview, strip_anki_html


class ExportError(RuntimeError):
    """A printable export could not be written."""


@dataclass(frozen=True)
class _PagePlan:
    landscape: bool
    width: int
    height: int
    margin: int
    header: int
    grid_x: int
    grid_y: int
    cell: int
    clue_x: int
    clue_top: int
    clue_bottom: int


def export_puzzle_pdf(path: str | Path, puzzle: Puzzle, *, title: str) -> None:
    """Write an A4 puzzle PDF with an empty grid and newspaper-style clues."""
    _write_pdf(path, puzzle, title=title, include_answers=False)


def export_answer_pdf(path: str | Path, puzzle: Puzzle, *, title: str) -> None:
    """Write an A4 answer-key PDF with identical grid geometry."""
    _write_pdf(path, puzzle, title=title, include_answers=True)


def export_puzzle_png(path: str | Path, puzzle: Puzzle, *, title: str) -> None:
    """Write the one-page puzzle as a 300 DPI PNG."""
    _write_png(path, puzzle, title=title, include_answers=False)


def export_answer_png(path: str | Path, puzzle: Puzzle, *, title: str) -> None:
    """Write the matching answer key as a 300 DPI PNG."""
    _write_png(path, puzzle, title=title, include_answers=True)


def export_puzzle_svg(path: str | Path, puzzle: Puzzle, *, title: str) -> None:
    """Write the one-page puzzle as scalable vector graphics."""
    _write_svg(path, puzzle, title=title, include_answers=False)


def export_answer_svg(path: str | Path, puzzle: Puzzle, *, title: str) -> None:
    """Write the matching answer key as scalable vector graphics."""
    _write_svg(path, puzzle, title=title, include_answers=True)


def configure_a4_device(device, puzzle: Puzzle) -> None:
    """Configure a Qt paint device for the same A4 geometry used in exports."""
    from aqt.qt import QPageLayout, QPageSize

    plan = _page_plan(puzzle, resolution=device.resolution())
    device.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    device.setPageOrientation(
        QPageLayout.Orientation.Landscape
        if plan.landscape
        else QPageLayout.Orientation.Portrait
    )


def render_to_device(device, puzzle: Puzzle, *, title: str, include_answers: bool) -> None:
    """Paint the single-page newspaper layout to a configured Qt print device."""
    from aqt.qt import QPainter

    plan = _page_plan(puzzle, resolution=device.resolution())
    painter = QPainter(device)
    if not painter.isActive():
        raise ExportError("Anki could not prepare the PDF preview.")
    try:
        _draw_one_page(painter, plan, puzzle, title, include_answers)
    finally:
        painter.end()


def _write_pdf(
    path: str | Path,
    puzzle: Puzzle,
    *,
    title: str,
    include_answers: bool,
) -> None:
    try:
        from aqt.qt import QPdfWriter
    except ImportError as exc:  # pragma: no cover - only Anki provides Qt
        raise ExportError("PDF export is available inside Anki Desktop.") from exc

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    writer = QPdfWriter(str(target))
    writer.setResolution(300)
    writer.setTitle(title)
    writer.setCreator("Anki Crossword Generator")
    configure_a4_device(writer, puzzle)
    render_to_device(writer, puzzle, title=title, include_answers=include_answers)

    if not target.exists() or target.stat().st_size < 100:
        raise ExportError("The PDF file was not created successfully.")


def _write_png(
    path: str | Path,
    puzzle: Puzzle,
    *,
    title: str,
    include_answers: bool,
) -> None:
    """Rasterise the same A4 layout used by PDF at print resolution."""
    try:
        from aqt.qt import QImage, QPainter
    except ImportError as exc:  # pragma: no cover - only Anki provides Qt
        raise ExportError("PNG export is available inside Anki Desktop.") from exc

    resolution = 300
    plan = _page_plan(puzzle, resolution=resolution)
    image = QImage(plan.width, plan.height, QImage.Format.Format_ARGB32)
    image.fill(0xFFFFFFFF)
    dots_per_meter = round(resolution / 0.0254)
    image.setDotsPerMeterX(dots_per_meter)
    image.setDotsPerMeterY(dots_per_meter)
    painter = QPainter(image)
    if not painter.isActive():
        raise ExportError("Anki could not prepare the PNG export.")
    try:
        _draw_one_page(painter, plan, puzzle, title, include_answers)
    finally:
        painter.end()
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if not image.save(str(target), "PNG") or not target.exists() or target.stat().st_size < 100:
        raise ExportError("The PNG file was not created successfully.")


def _write_svg(
    path: str | Path,
    puzzle: Puzzle,
    *,
    title: str,
    include_answers: bool,
) -> None:
    """Write the same page layout to Qt's SVG paint device."""
    try:
        from aqt.qt import QPainter, QRect, QSize
        from PyQt6.QtSvg import QSvgGenerator
    except ImportError as exc:  # pragma: no cover - optional Qt module
        raise ExportError("SVG export is not available in this Anki installation.") from exc

    resolution = 300
    plan = _page_plan(puzzle, resolution=resolution)
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    generator = QSvgGenerator()
    generator.setFileName(str(target))
    generator.setSize(QSize(plan.width, plan.height))
    generator.setViewBox(QRect(0, 0, plan.width, plan.height))
    generator.setResolution(resolution)
    generator.setTitle(title)
    generator.setDescription("Anki Crossword Generator")
    painter = QPainter(generator)
    if not painter.isActive():
        raise ExportError("Anki could not prepare the SVG export.")
    try:
        _draw_one_page(painter, plan, puzzle, title, include_answers)
    finally:
        painter.end()
    if not target.exists() or target.stat().st_size < 100:
        raise ExportError("The SVG file was not created successfully.")


def _page_plan(puzzle: Puzzle, *, resolution: int) -> _PagePlan:
    """Plan one landscape A4 page: grid left, Across/Down columns right."""
    portrait = (round(8.27 * resolution), round(11.69 * resolution))
    width, height = portrait[1], portrait[0]
    margin = round(0.48 * resolution)
    header = round(0.75 * resolution)
    grid_column_right = round(width * 0.47)
    available_w = grid_column_right - margin
    footer = round(0.25 * resolution)
    available_h = height - 2 * margin - header - footer
    natural_cell = min(available_w // puzzle.cols, available_h // puzzle.rows)
    # Leave breathing room around the grid instead of filling the entire left
    # column. This reads more like a newspaper puzzle than a software export.
    cell = max(18, round(natural_cell * 0.74))
    grid_w = cell * puzzle.cols
    grid_h = cell * puzzle.rows
    # Centre only inside the left grid column; centring across the full page
    # would overlap the right-hand clue columns.
    grid_x = margin + max(0, (available_w - grid_w) // 2)
    grid_y = margin + header
    clue_x = round(width * 0.50)
    clue_top = grid_y + max(42, round(cell * 0.55))
    clue_bottom = height - margin - footer
    return _PagePlan(
        True,
        width,
        height,
        margin,
        header,
        grid_x,
        grid_y,
        cell,
        clue_x,
        clue_top,
        clue_bottom,
    )


def _draw_one_page(painter, plan: _PagePlan, puzzle: Puzzle, title: str, answers: bool) -> None:
    from aqt.qt import QColor, QFont, QPen, Qt

    painter.fillRect(0, 0, plan.width, plan.height, QColor("#ffffff"))
    title_px = max(56, round(plan.cell * 0.8))
    date_px = max(38, round(title_px * 0.68))
    painter.setPen(QColor("#151515"))
    title_font = _print_font()
    title_font.setPixelSize(title_px)
    title_font.setBold(True)
    painter.setFont(title_font)
    baseline = plan.margin + title_px
    painter.drawText(plan.margin, baseline, title)
    title_width = painter.fontMetrics().horizontalAdvance(title)
    date_font = _print_font()
    date_font.setPixelSize(date_px)
    date_font.setBold(False)
    date_font.setItalic(True)
    painter.setFont(date_font)
    painter.setPen(QColor("#3f3f3f"))
    painter.drawText(plan.margin + title_width + date_px // 2, baseline, f"- {_long_date()}")
    painter.setPen(QPen(QColor("#151515"), max(1, plan.cell // 26)))
    rule_y = baseline + max(18, round(date_px * 0.55))
    painter.drawLine(plan.margin, rule_y, plan.width - plan.margin, rule_y)

    number_map = {(entry.row, entry.col): entry.number for entry in puzzle.entries}
    for row in range(puzzle.rows):
        for col in range(puzzle.cols):
            x = plan.grid_x + col * plan.cell
            y = plan.grid_y + row * plan.cell
            letter = puzzle.letter_at(row, col)
            if letter is None:
                painter.fillRect(x, y, plan.cell, plan.cell, QColor("#151515"))
                continue
            painter.fillRect(x, y, plan.cell, plan.cell, QColor("#ffffff"))
            painter.setPen(QPen(QColor("#151515"), max(1, plan.cell // 30)))
            painter.drawRect(x, y, plan.cell, plan.cell)
            number = number_map.get((row, col))
            if number is not None:
                _set_font(painter, _print_font(), max(10, round(plan.cell * 0.2)), bold=False)
                painter.drawText(
                    x + max(3, plan.cell // 12),
                    y + round(plan.cell * 0.25),
                    str(number),
                )
            if answers:
                _set_font(painter, _print_font(), max(14, round(plan.cell * 0.5)), bold=True)
                painter.drawText(
                    x,
                    y,
                    plan.cell,
                    plan.cell + max(2, plan.cell // 20),
                    int(Qt.AlignmentFlag.AlignCenter),
                    letter,
                )

    painter.setPen(QColor("#151515"))
    column_width = plan.width - plan.clue_x - plan.margin
    section_gap = max(32, plan.cell // 2)
    across_entries = puzzle.across()
    down_entries = puzzle.down()
    available_height = plan.clue_bottom - plan.clue_top - section_gap
    if not across_entries:
        across_bottom = plan.clue_top
        down_top = plan.clue_top
    elif not down_entries:
        across_bottom = plan.clue_bottom
        down_top = plan.clue_bottom
    else:
        total_entries = len(across_entries) + len(down_entries)
        across_height = max(
            round(available_height * len(across_entries) / total_entries),
            round(available_height * 0.28),
        )
        across_bottom = min(plan.clue_bottom - section_gap, plan.clue_top + across_height)
        down_top = across_bottom + section_gap
    _draw_clue_column(
        painter,
        across_entries,
        "Across",
        plan.clue_x,
        plan.clue_top,
        column_width,
        across_bottom,
        plan.cell,
        _fit_clue_body_size(
            across_entries,
            column_width,
            plan.clue_top,
            across_bottom,
            plan.cell,
            answers,
        ),
        answers,
    )
    _draw_clue_column(
        painter,
        down_entries,
        "Down",
        plan.clue_x,
        down_top,
        column_width,
        plan.clue_bottom,
        plan.cell,
        _fit_clue_body_size(
            down_entries,
            column_width,
            down_top,
            plan.clue_bottom,
            plan.cell,
            answers,
        ),
        answers,
    )


def _draw_clue_column(
    painter,
    entries: Iterable[PlacedEntry],
    heading: str,
    x: int,
    top: int,
    width: int,
    bottom: int,
    cell: int,
    body_px: int,
    answers: bool,
) -> None:
    from aqt.qt import QColor, QRectF

    painter.setPen(QColor("#151515"))
    _set_font(painter, _print_font(), max(30, round(cell * 0.52)), bold=True)
    painter.drawText(x, top, heading)
    y = top + max(22, round(cell * 0.48))
    for entry in entries:
        document = _clue_document(entry, width, body_px, answers)
        required = max(17, round(document.size().height())) + max(7, body_px // 3)
        if y + required > bottom:
            break
        painter.save()
        painter.translate(x, y)
        document.drawContents(painter, QRectF(0, 0, width, required))
        painter.restore()
        y += required


def _clue_document(entry: PlacedEntry, width: int, body_px: int, answers: bool):
    """Create a safe rich-text clue document for the print renderer."""
    from aqt.qt import QTextDocument

    source = entry.answer_text if answers else _pdf_clue_html(entry)
    document = QTextDocument()
    font = _print_font()
    font.setPixelSize(body_px)
    document.setDefaultFont(font)
    document.setDefaultStyleSheet(
        "b, strong, mark, em { font-weight: bold; text-decoration: underline; } "
        "u { text-decoration: underline; }"
    )
    document.setHtml(
        f'<html><body style="margin:0; color:#151515; font-size:{body_px}px;">'
        f'<span style="font-weight:bold">{entry.number}.</span>&nbsp;{source} '
        f'<span style="color:#555555">({entry.length})</span>'
        "</body></html>"
    )
    document.setTextWidth(width)
    return document


def _clue_body_size(top: int, bottom: int, count: int, cell: int) -> int:
    """Use readable clue type while guaranteeing a one-page layout."""
    height = max(1, bottom - top)
    # A typical puzzle has about ten clues in each section. Full-width clue
    # sections need less wrap allowance than narrow newspaper columns, so this
    # keeps the default 20-clue worksheet comfortably readable.
    line_budget = round(max(1, count) * 1.55 + 3)
    return max(32, min(round(cell * 0.6), height // line_budget))


def _fit_clue_body_size(
    entries: Iterable[PlacedEntry],
    width: int,
    top: int,
    bottom: int,
    cell: int,
    answers: bool,
) -> int:
    """Find the largest type size that fits the actual wrapped clues."""
    items = tuple(entries)
    preferred = _clue_body_size(top, bottom, len(items), cell)
    for size in range(preferred, 17, -1):
        y = top + max(22, round(cell * 0.48))
        for entry in items:
            document = _clue_document(entry, width, size, answers)
            y += max(17, round(document.size().height())) + max(7, size // 3)
        if y <= bottom:
            return size
    return 18


def _wrap_text(text: str, width: int, pixel_size: int) -> list[str]:
    """Wrap plain clue text conservatively using Qt font metrics."""
    from aqt.qt import QFontMetrics

    font = _print_font()
    font.setPixelSize(pixel_size)
    metrics = QFontMetrics(font)
    words = text.split()
    if not words:
        return [""]
    lines: list[str] = []
    line = ""
    for word in words:
        candidate = word if not line else f"{line} {word}"
        if line and metrics.horizontalAdvance(candidate) > width:
            lines.append(line)
            line = word
        else:
            line = candidate
    if line:
        lines.append(line)
    return lines


def _plain_clue(entry: PlacedEntry) -> str:
    raw = entry.clue_html or entry.clue or entry.display_text
    return " ".join(strip_anki_html(raw).split())


def _pdf_clue_html(entry: PlacedEntry) -> str:
    """Keep Anki emphasis but render marked words as bold, underlined print text."""
    raw = entry.clue_html or entry.clue or entry.display_text
    raw = re.sub(r"</?(?:div|p|li|section|article)\b[^>]*>", "", raw, flags=re.I)
    # The underline mode converts Anki <mark>, coloured spans, and highlighter
    # classes into an ink-only mark that remains legible on a photocopied PDF.
    rendered = anki_html_for_preview(
        raw,
        dark=False,
        mark_style="underline",
        mark_color="black",
        mark_text="black",
    )
    return re.sub(
        r"(text-decoration\s*:\s*underline)(?![^\"']*(?:font-weight\s*:))",
        r"\1; font-weight:bold",
        rendered,
        flags=re.IGNORECASE,
    )


def _long_date() -> str:
    """Return the current date in the masthead's long form."""
    today = date.today()
    return f"{today.strftime('%B')} {today.day}, {today.year}"


def _print_font():
    """Choose an installed font with good Japanese coverage when available."""
    from aqt.qt import QFont, QFontDatabase

    families = {name.casefold(): name for name in QFontDatabase.families()}
    for preferred in (
        "Noto Sans CJK JP",
        "Noto Sans JP",
        "Yu Gothic",
        "Meiryo",
        "Hiragino Sans",
        "MS Gothic",
    ):
        match = families.get(preferred.casefold())
        if match:
            return QFont(match)
    return QFont()


def _set_font(painter, font, pixel_size: int, *, bold: bool) -> None:
    font.setPixelSize(max(8, pixel_size))
    font.setBold(bold)
    painter.setFont(font)
