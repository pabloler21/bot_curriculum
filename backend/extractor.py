import logging
import os
import re
import tempfile

from liteparse import LiteParse
from liteparse.types import ParseError

logger = logging.getLogger(__name__)
parser = LiteParse()

# Characters that render as nothing but are still read by the model: the vector
# for CVs carrying hidden instructions or fake experience. Covers C0 controls,
# soft hyphen, zero-width and bidi controls, BOM and the Unicode tag block
# (U+E0000-U+E007F), which is how invisible text is usually smuggled in.
# ponytail: text hidden by colour (white-on-white) is NOT detectable here --
# liteparse exposes no colour, and white text on a dark banner is a legitimate
# CV design. The prompts treat CV text as data, never as instructions, instead.
_INVISIBLE = re.compile(
    "[\x00-\x08\x0b\x0c\x0e-\x1f\x7f"
    "\u00ad\u200b-\u200f\u202a-\u202e"
    "\u2060-\u2064\u2066-\u206f\ufeff\ufff9-\ufffb"
    "\U000e0000-\U000e007f]"
)


def strip_invisible(text: str) -> str:
    """Remove characters a human cannot see but the LLM would read as content."""
    return _INVISIBLE.sub("", text)


def extract_text(file_bytes: bytes, file_name: str) -> str:
    extension = os.path.splitext(file_name)[1]

    with tempfile.NamedTemporaryFile(delete=False, suffix=extension) as tmp:
        tmp.write(file_bytes)
        temp_path = tmp.name

    try:
        result = parser.parse(temp_path)
        return strip_invisible(result.text)
    except ParseError as e:
        detail = str(e)
        if e.stderr:
            detail += f" | stderr: {e.stderr}"
        raise RuntimeError(detail)
    finally:
        os.remove(temp_path)
