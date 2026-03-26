import tempfile
import os
from liteparse import LiteParse

# instancia unica del parser, se reutiliza en cada llamada
parser = LiteParse()

def extract_text(file_bytes: bytes, file_name: str) -> str:
    # extraemos la extension del archivo original (.pdf, .png, .docx, etc)
    extension = os.path.splitext(file_name)[1]

    # creamos un archivo temporal en disco con la extension correcta
    # liteparse necesita una ruta real, no puede leer bytes directamente
    with tempfile.NamedTemporaryFile(delete=False, suffix=extension) as tmp:
        tmp.write(file_bytes)
        temp_path = tmp.name

    try:
        # parseamos el archivo y devolvemos el texto extraido
        result = parser.parse(temp_path)
        return result.text
    finally:
        # borramos el archivo temporal siempre, incluso si hay un error
        os.remove(temp_path)