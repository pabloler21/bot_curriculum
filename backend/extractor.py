import io
import logging
import os
import re
import tempfile

import pdfplumber
from liteparse import LiteParse
from liteparse.types import ParseError

logger = logging.getLogger(__name__)
parser = LiteParse()

# Characters that render as nothing but are still read by the model: the vector
# for CVs carrying hidden instructions or fake experience. Covers C0 controls,
# soft hyphen, zero-width and bidi controls, BOM and the Unicode tag block
# (U+E0000-U+E007F), which is how invisible text is usually smuggled in.
_INVISIBLE = re.compile(
    "[\x00-\x08\x0b\x0c\x0e-\x1f\x7f"
    "\u00ad\u200b-\u200f\u202a-\u202e"
    "\u2060-\u2064\u2066-\u206f\ufeff\ufff9-\ufffb"
    "\U000e0000-\U000e007f]"
)

# ── Hidden-text filtering for PDFs ────────────────────────────────────────────
# liteparse gives us no glyph colour, so white-on-white text reaches the model as
# genuine CV content. pdfplumber exposes colour, size and position per character,
# which is the only layer where hidden text can still be told apart from real text.
_MIN_SIZE = 4.0  # pt — below this a glyph is not legible to a human
_WHITE = 0.85  # fill component at or above this counts as page-white


def strip_invisible(text: str) -> str:
    """Remove characters a human cannot see but the LLM would read as content."""
    return _INVISIBLE.sub("", text)


def _near_white(color) -> bool:
    """True if a fill colour is effectively the white of the page."""
    if color is None:
        return False  # pdfminer's default is black — visible
    if isinstance(color, (int, float)):
        return color >= _WHITE  # DeviceGray
    try:
        return all(c >= _WHITE for c in color)  # DeviceRGB/CMYK tuples
    except TypeError:
        return False


def _dark_backdrops(page) -> list[dict]:
    """Filled shapes dark enough to make white text on top of them readable.

    Without this, the naive "drop every near-white glyph" rule deletes the
    candidate's own contact details: a dark sidebar with white text is a common
    CV template, not an attack.
    """
    return [
        shape
        for shape in (page.rects + page.curves)
        if shape.get("fill") and not _near_white(shape.get("non_stroking_color"))
    ]


def _on_dark_backdrop(ch: dict, backdrops: list[dict]) -> bool:
    cx = (ch["x0"] + ch["x1"]) / 2
    cy = (ch["top"] + ch["bottom"]) / 2
    return any(
        shape["x0"] <= cx <= shape["x1"] and shape["top"] <= cy <= shape["bottom"]
        for shape in backdrops
    )


def _visible_char(ch: dict, page_w: float, page_h: float, backdrops: list[dict]) -> bool:
    if ch.get("size", 0) < _MIN_SIZE:  # tiny font
        return False
    if ch["top"] < 0 or ch["bottom"] > page_h or ch["x0"] < 0 or ch["x1"] > page_w:
        return False  # drawn outside the page
    if _near_white(ch.get("non_stroking_color")):  # white on white
        return _on_dark_backdrop(ch, backdrops)
    return True


def _visible_pdf_text(file_bytes: bytes) -> str | None:
    """Text a human would actually see on the page.

    Returns None when there is nothing to read at the glyph level — a scanned
    PDF or one we cannot open — so the caller can fall back to OCR. A PDF that
    *has* a text layer always returns its visible part, even if that part is
    short: falling back on a short result would let an attacker bypass the whole
    filter by keeping the visible half of the CV small.

    ponytail: colour, size and position only. pdfplumber exposes no text render
    mode and no alpha, so `3 Tr` and opacity-0 glyphs still get through, as does
    text covered by an opaque image. Needs a pdfminer-level reader to close those.
    """
    parts = []
    has_text_layer = False
    try:
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for page in pdf.pages:
                width, height = page.width, page.height
                backdrops = _dark_backdrops(page)
                has_text_layer = has_text_layer or bool(page.chars)
                kept = page.filter(
                    lambda obj: obj.get("object_type") != "char"
                    or _visible_char(obj, width, height, backdrops)
                )
                parts.append(kept.extract_text() or "")
    except Exception as exc:  # malformed/encrypted PDF — let liteparse try
        logger.warning("[extractor] pdfplumber could not read the PDF: %s", exc)
        return None

    return "\n".join(parts).strip() if has_text_layer else None


def _liteparse_text(file_bytes: bytes, file_name: str) -> str:
    extension = os.path.splitext(file_name)[1]

    with tempfile.NamedTemporaryFile(delete=False, suffix=extension) as tmp:
        tmp.write(file_bytes)
        temp_path = tmp.name

    try:
        result = parser.parse(temp_path)
        return result.text
    except ParseError as e:
        detail = str(e)
        if e.stderr:
            detail += f" | stderr: {e.stderr}"
        raise RuntimeError(detail)
    finally:
        os.remove(temp_path)


def extract_text(file_bytes: bytes, file_name: str) -> str:
    if os.path.splitext(file_name)[1].lower() == ".pdf":
        text = _visible_pdf_text(file_bytes)
        if text is not None:
            return strip_invisible(text)
        # No text layer at all: scanned PDF, hand it to liteparse's OCR
        logger.info("[extractor] PDF has no text layer — falling back to OCR")

    return strip_invisible(_liteparse_text(file_bytes, file_name))
