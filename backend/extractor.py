from liteparse import LiteParse

def extraer_texto(ruta_archivo: str) -> str:
    parser = LiteParse()
    resultado = parser.parse(ruta_archivo)
    return resultado.text