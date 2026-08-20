# SPDX-License-Identifier: GPL-3.0-or-later
"""Plain-text extraction from Anki field HTML for preview and validity."""

from __future__ import annotations

import html
import re
import unicodedata

SOUND_RE = re.compile(r"\[sound:[^\]]*\]", re.IGNORECASE)
STYLE_RE = re.compile(r"<style\b[^>]*>.*?</style>", re.IGNORECASE | re.DOTALL)
SCRIPT_RE = re.compile(r"<script\b[^>]*>.*?</script>", re.IGNORECASE | re.DOTALL)
RUBY_RE = re.compile(r"<rt\b[^>]*>.*?</rt>|<rp\b[^>]*>.*?</rp>", re.IGNORECASE | re.DOTALL)
BREAK_RE = re.compile(
    r"<br\s*/?>|</(?:p|div|li|tr|h[1-6]|blockquote|section|article)\s*>",
    re.IGNORECASE,
)
TAG_RE = re.compile(r"<[^>]+>")
SPACE_RE = re.compile(r"\s+")
UNSAFE_TAG_RE = re.compile(
    r"</?(?:img|iframe|object|embed|video|audio|link|meta|form|input|button)\b[^>]*>",
    re.IGNORECASE,
)
_MARK_OPEN_RE = re.compile(r"<mark\b[^>]*>", re.IGNORECASE)
_MARK_CLOSE_RE = re.compile(r"</mark>", re.IGNORECASE)
_RGB_RE = re.compile(
    r"rgba?\(\s*(\d+)\s*[, ]\s*(\d+)\s*[, ]\s*(\d+)(?:\s*[,/]\s*[\d.]+)?\s*\)",
    re.IGNORECASE,
)
_BG_NAMED_RE = re.compile(
    r"(background-color\s*:\s*)([a-z]+)\b",
    re.IGNORECASE,
)
_HL_OPEN_RE = re.compile(
    r"<(span|font)(?=[^>]*class=['\"][^'\"]*(?:highlight|hlite)[^'\"]*['\"])[^>]*>",
    re.IGNORECASE,
)
_NAMED_COLORS = {
    "yellow": "#ffff00",
    "gold": "#ffd700",
    "orange": "#ffa500",
    "pink": "#ffc0cb",
    "red": "#ff0000",
    "lime": "#00ff00",
    "aqua": "#00ffff",
    "cyan": "#00ffff",
    "magenta": "#ff00ff",
    "fuchsia": "#ff00ff",
    "blue": "#0000ff",
    "green": "#008000",
    "white": "#ffffff",
    "black": "#000000",
}
# Light UI: Material amber 200. Dark UI: dusty gold — same hue, far less glare.
_LIGHT_HL_BG = "#ffe082"
_LIGHT_HL_FG = "#1a1a1a"
_DARK_HL_BG = "#bfa14a"
_DARK_HL_FG = "#1a1408"
_EMPHASIS_OPEN_RE = re.compile(r"<(b|strong|mark|em)(\s[^>]*)?>", re.IGNORECASE)
_MARK_COLOR_PAIRS = {
    "black": ("#000000", "#ff2d2d", "#000000", "#ff2d2d"),
    "gold": ("#bfa14a", "#1a1408", "#ffe082", "#1a1a1a"),
    "green": ("#6a9e73", "#102014", "#a9d4ae", "#142016"),
    "pink": ("#c989a4", "#1a1014", "#f4c1d1", "#1a1216"),
    "blue": ("#7a96c4", "#10141a", "#a8c4ea", "#12161a"),
}
_MARK_TEXT_COLORS = {
    "red": "#ff2d2d",
    "white": "#f5f5f5",
    "black": "#1a1408",
    "gold": "#ffe082",
}
_STYLE_ATTR_RE = re.compile(r'(style\s*=\s*)(["\'])(.*?)\2', re.IGNORECASE | re.DOTALL)
_INK = (0x1A, 0x14, 0x08)
_CREAM = (0xF6, 0xED, 0xC4)


def strip_anki_html(value: str | None) -> str:
    """Return visible text from an Anki field, without executing HTML."""
    if not value:
        return ""
    text = SOUND_RE.sub("", value)
    text = STYLE_RE.sub("", text)
    text = SCRIPT_RE.sub("", text)
    text = RUBY_RE.sub("", text)
    text = BREAK_RE.sub(" ", text)
    text = TAG_RE.sub("", text)
    text = html.unescape(text)
    text = SPACE_RE.sub(" ", text)
    return text.strip()


def anki_html_for_preview(
    value: str | None,
    *,
    dark: bool = False,
    mark_style: str = "highlight",
    mark_color: str = "black",
    mark_text: str = "red",
) -> str:
    """Keep bold, italic, underline, and highlights for Qt rich-text preview.

    Anki stores highlighter colours as ``rgb()``; Qt's rich-text engine only
    reliably paints ``#RRGGBB``, so colours are normalised here. Words marked
    bold or highlighted on the card are painted with the chosen clue-mark
    style so they stay obvious on the crossword clue list.
    """
    if not value:
        return ""
    style = (mark_style or "highlight").strip().lower()
    color = (mark_color or "black").strip().lower()
    text_color = (mark_text or "red").strip().lower()
    bg, fg = _mark_paint_colors(color, dark=dark)
    fg = _MARK_TEXT_COLORS.get(text_color, fg)
    text = SOUND_RE.sub("", value)
    text = STYLE_RE.sub("", text)
    text = SCRIPT_RE.sub("", text)
    text = UNSAFE_TAG_RE.sub("", text)
    text = _MARK_OPEN_RE.sub(
        f'<span style="{_emphasis_css(style, bg, fg)}">', text
    )
    text = _MARK_CLOSE_RE.sub("</span>", text)
    text = _HL_OPEN_RE.sub(
        lambda match: _inject_highlight_style(match, css=_emphasis_css(style, bg, fg)),
        text,
    )
    text = _RGB_RE.sub(_rgb_to_hex, text)
    text = _BG_NAMED_RE.sub(_named_bg_to_hex, text)
    text = _adapt_highlight_styles(
        text,
        dark=dark,
        mark_style=style,
        mark_color=color,
        bg=bg,
        fg=fg,
        force_text=text_color in _MARK_TEXT_COLORS,
    )
    text = _paint_emphasis_tags(text, _emphasis_css(style, bg, fg))
    text = text.strip()
    if "<" not in text:
        return html.escape(text)
    return text


def _rgb_to_hex(match: re.Match[str]) -> str:
    red, green, blue = (min(255, int(match.group(i))) for i in (1, 2, 3))
    return f"#{red:02x}{green:02x}{blue:02x}"


def _named_bg_to_hex(match: re.Match[str]) -> str:
    hex_color = _NAMED_COLORS.get(match.group(2).lower())
    if not hex_color:
        return match.group(0)
    return match.group(1) + hex_color


def _inject_highlight_style(match: re.Match[str], *, css: str) -> str:
    tag = match.group(0)
    if re.search(r"background(?:-color)?\s*:", tag, re.IGNORECASE):
        return tag
    return tag[:-1] + f' style="{css}">'


def _emphasis_css(style: str, bg: str, fg: str) -> str:
    bits: list[str] = []
    if style in {"highlight", "highlight_bold"}:
        bits.append(f"background-color:{bg}")
    bits.append(f"color:{fg}")
    if style in {"bold", "highlight_bold"}:
        bits.append("font-weight:bold")
    if style == "underline":
        bits.append("text-decoration:underline")
    return "; ".join(bits)


def _mark_paint_colors(name: str, *, dark: bool) -> tuple[str, str]:
    pair = _MARK_COLOR_PAIRS.get(name)
    if pair is None:
        return (_DARK_HL_BG, _DARK_HL_FG) if dark else (_LIGHT_HL_BG, _LIGHT_HL_FG)
    dark_bg, dark_fg, light_bg, light_fg = pair
    return (dark_bg, dark_fg) if dark else (light_bg, light_fg)


def _paint_emphasis_tags(html: str, css: str) -> str:
    if not css:
        return html

    def repl(match: re.Match[str]) -> str:
        tag = match.group(1)
        rest = match.group(2) or ""
        if re.search(r"\bstyle\s*=", rest, re.IGNORECASE):
            rest = re.sub(
                r'(style\s*=\s*)(["\'])(.*?)\2',
                lambda style_match: (
                    f"{style_match.group(1)}{style_match.group(2)}"
                    f"{css}; {style_match.group(3)}{style_match.group(2)}"
                ),
                rest,
                count=1,
                flags=re.IGNORECASE,
            )
            return f"<{tag}{rest}>"
        return f'<{tag}{rest} style="{css}">'

    return _EMPHASIS_OPEN_RE.sub(repl, html)


def _adapt_highlight_styles(
    html: str,
    *,
    dark: bool,
    mark_style: str,
    mark_color: str,
    bg: str,
    fg: str,
    force_text: bool,
) -> str:
    def repl(match: re.Match[str]) -> str:
        style = _adapt_style_block(
            match.group(3),
            dark=dark,
            mark_style=mark_style,
            mark_color=mark_color,
            bg=bg,
            fg=fg,
            force_text=force_text,
        )
        return f"{match.group(1)}{match.group(2)}{style}{match.group(2)}"

    return _STYLE_ATTR_RE.sub(repl, html)


def _adapt_style_block(
    style: str,
    *,
    dark: bool,
    mark_style: str,
    mark_color: str,
    bg: str,
    fg: str,
    force_text: bool,
) -> str:
    decls = [part.strip() for part in style.split(";") if part.strip()]
    props: dict[str, str] = {}
    order: list[str] = []
    for decl in decls:
        if ":" not in decl:
            continue
        key, value = decl.split(":", 1)
        name = key.strip().lower()
        if name not in props:
            order.append(name)
        props[name] = value.strip()
    bg_key = "background-color" if "background-color" in props else (
        "background" if "background" in props else ""
    )
    if not bg_key:
        return style
    parsed = _parse_css_color(props[bg_key])
    if parsed is None:
        return style
    if mark_style in {"bold", "underline"}:
        props.pop("background-color", None)
        props.pop("background", None)
        order = [name for name in order if name not in {"background-color", "background"}]
        if mark_style == "bold":
            props["font-weight"] = "bold"
            if "font-weight" not in order:
                order.append("font-weight")
        else:
            props["text-decoration"] = "underline"
            if "text-decoration" not in order:
                order.append("text-decoration")
        props["color"] = fg
        if "color" not in order:
            order.append("color")
        return "; ".join(f"{name}: {props[name]}" for name in order if name in props)
    if mark_color != "theme":
        new_bg, new_fg = bg, fg
    else:
        new_bg, new_fg = _highlight_pair(parsed, dark=dark)
        if force_text:
            new_fg = fg
    props["background-color"] = new_bg
    props["color"] = new_fg
    if mark_style == "highlight_bold":
        props["font-weight"] = "bold"
        if "font-weight" not in order:
            order.append("font-weight")
    if bg_key == "background":
        order = ["background-color" if name == "background" else name for name in order]
        props.pop("background", None)
    if "color" not in order:
        order.append("color")
    return "; ".join(f"{name}: {props[name]}" for name in order if name in props)


def _highlight_pair(rgb: tuple[int, int, int], *, dark: bool) -> tuple[str, str]:
    if _is_yellowish(*rgb):
        if dark:
            return _DARK_HL_BG, _DARK_HL_FG
        return _LIGHT_HL_BG, _LIGHT_HL_FG
    luminance = _relative_luminance(*rgb)
    if dark and luminance > 0.40:
        hue, sat, _light = _rgb_to_hsl(*rgb)
        muted = _hsl_to_rgb(hue, min(sat, 0.55), 0.42)
        return _hex(*muted), _DARK_HL_FG
    if not dark and luminance > 0.85:
        hue, sat, _light = _rgb_to_hsl(*rgb)
        pastel = _hsl_to_rgb(hue, min(sat, 0.70), 0.86)
        return _hex(*pastel), _LIGHT_HL_FG
    ink_contrast = _contrast(rgb, _INK)
    cream_contrast = _contrast(rgb, _CREAM)
    fg = _INK if ink_contrast >= cream_contrast else _CREAM
    return _hex(*rgb), _hex(*fg)


def _is_yellowish(red: int, green: int, blue: int) -> bool:
    return red >= 180 and green >= 160 and blue <= 150 and red + green > blue * 3


def _parse_css_color(value: str) -> tuple[int, int, int] | None:
    token = value.strip().lower()
    named = _NAMED_COLORS.get(token)
    if named:
        return _hex_to_rgb(named)
    if token.startswith("#"):
        return _hex_to_rgb(token)
    return None


def _hex_to_rgb(value: str) -> tuple[int, int, int] | None:
    hex_value = value.strip().lstrip("#")
    if len(hex_value) == 3:
        hex_value = "".join(char * 2 for char in hex_value)
    if len(hex_value) != 6 or any(char not in "0123456789abcdef" for char in hex_value.lower()):
        return None
    return tuple(int(hex_value[i : i + 2], 16) for i in (0, 2, 4))


def _hex(red: int, green: int, blue: int) -> str:
    return f"#{red:02x}{green:02x}{blue:02x}"


def _relative_luminance(red: int, green: int, blue: int) -> float:
    return (
        0.2126 * _linear_channel(red)
        + 0.7152 * _linear_channel(green)
        + 0.0722 * _linear_channel(blue)
    )


def _linear_channel(value: int) -> float:
    channel = value / 255
    if channel <= 0.04045:
        return channel / 12.92
    return ((channel + 0.055) / 1.055) ** 2.4


def _contrast(first: tuple[int, int, int], second: tuple[int, int, int]) -> float:
    light = max(_relative_luminance(*first), _relative_luminance(*second))
    dark = min(_relative_luminance(*first), _relative_luminance(*second))
    return (light + 0.05) / (dark + 0.05)


def _rgb_to_hsl(red: int, green: int, blue: int) -> tuple[float, float, float]:
    r_n, g_n, b_n = red / 255, green / 255, blue / 255
    max_c, min_c = max(r_n, g_n, b_n), min(r_n, g_n, b_n)
    light = (max_c + min_c) / 2
    if max_c == min_c:
        return 0.0, 0.0, light
    delta = max_c - min_c
    sat = delta / (2 - max_c - min_c) if light > 0.5 else delta / (max_c + min_c)
    if max_c == r_n:
        hue = (g_n - b_n) / delta + (6 if g_n < b_n else 0)
    elif max_c == g_n:
        hue = (b_n - r_n) / delta + 2
    else:
        hue = (r_n - g_n) / delta + 4
    return hue / 6, sat, light


def _hsl_to_rgb(hue: float, sat: float, light: float) -> tuple[int, int, int]:
    if sat == 0:
        value = round(light * 255)
        return value, value, value

    def hue_to_channel(p: float, q: float, t: float) -> float:
        if t < 0:
            t += 1
        if t > 1:
            t -= 1
        if t < 1 / 6:
            return p + (q - p) * 6 * t
        if t < 1 / 2:
            return q
        if t < 2 / 3:
            return p + (q - p) * (2 / 3 - t) * 6
        return p

    q = light * (1 + sat) if light < 0.5 else light + sat - light * sat
    p = 2 * light - q
    return (
        round(hue_to_channel(p, q, hue + 1 / 3) * 255),
        round(hue_to_channel(p, q, hue) * 255),
        round(hue_to_channel(p, q, hue - 1 / 3) * 255),
    )


def normalize_for_dedupe(text: str) -> str:
    """Stable key used to merge cards that share the same crossword answer.

    Phase 1 uses Unicode NFC plus stripped text. Japanese cell tokenisation
    in a later phase will replace this with normalised kana cells.
    """
    return unicodedata.normalize("NFC", text).strip()


def truncate(text: str, limit: int = 120) -> str:
    """Shorten preview text without splitting a trailing surrogate pair."""
    if limit < 1 or len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"
