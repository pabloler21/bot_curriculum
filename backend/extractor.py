import logging
import os
import tempfile

from liteparse import LiteParse
from liteparse.types import ParseError

logger = logging.getLogger(__name__)
parser = LiteParse()


def extract_text(file_bytes: bytes, file_name: str) -> str:
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
