import tempfile
import os
from liteparse import LiteParse


parser = LiteParse()

def extract_text(file_bytes: bytes, file_name: str) -> str:
    
    extension = os.path.splitext(file_name)[1]

    
    with tempfile.NamedTemporaryFile(delete=False, suffix=extension) as tmp:
        tmp.write(file_bytes)
        temp_path = tmp.name

    try:
        
        result = parser.parse(temp_path)
        return result.text
    finally:
        
        os.remove(temp_path)