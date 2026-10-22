from nltk import re, SnowballStemmer
from pathlib import Path
import unicodedata
import nltk
import json

# Importa las relgas desde el json
ruta_reglas = Path('reglas.json').with_name('reglas.json')
reglas = None

# Crea un diccionario con las reglas del json para no modificar el código
with ruta_reglas.open(encoding='utf-8') as archivo:
    reglas = json.load(archivo)

# Inicialización del stemmer
stemmer = SnowballStemmer('spanish')

# Verifica que el texto sea válido, no sea nulo o esté vacío
def __texto_valido(texto: str) -> bool:
    return texto is not None and bool(re.search(r"\S", texto))

def normalizar_texto(texto: str | None) -> str:
    """
    Normaliza el texto, quitando los carácteres especiales, puntuaciones
    o inlcuso espacios duplicados, proceso antes de tokenizar
    """
    if not __texto_valido(texto):
        raise ValueError('No se pudo normalizar el texto porque el texto está vacío')
    
    texto = texto.lower().replace('ñ', '\0')
    texto = unicodedata.normalize('NFD', texto)
    texto = "".join(
        caracter
        for caracter in texto
        if unicodedata.category(caracter) != 'Mn'
    )
    texto = texto.replace('\0', 'ñ')
    texto = ''.join(
        caracter
        for caracter in texto
        if caracter.isalnum() or caracter.isspace()
    )

    return ' '.join(texto.split())

def tokenizar_y_stem(texto: str | None) -> tuple[list[str], list[str]]:
    texto_normalizado = normalizar_texto(texto)
    tokens = nltk.word_tokenize(texto_normalizado, language='spanish')
    stems = [stemmer.stem(token) for token in tokens]

    return tokens, stems

def detectar_intencion(texto: str | None) -> tuple[str, int]:
    tokens, stems = tokenizar_y_stem(texto)
    stems_mensaje = set(stems)
    candidatas = []
    umbral = reglas['configuracion']['umbral_minimo']

    for intencion in reglas['intenciones']:
        stems_clave = {
            stemmer.stem(token)
            for palabra in intencion['palabras_clave']
            for token in normalizar_texto(palabra).split()
        }
        puntuacion = len(stems_mensaje & stems_clave)

        for patron in intencion['patrones']:
            tokens_patron = normalizar_texto(patron).split()
            longitud_patron = len(tokens_patron)
            if any(
                tokens[indice:indice + longitud_patron] == tokens_patron
                for indice in range(len(tokens) - longitud_patron + 1)
            ):
                puntuacion += 1

        if puntuacion >= umbral:
            candidatas.append(
                (intencion['prioridad'], puntuacion, intencion['nombre'])
            )

    if not candidatas:
        return 'fallback', 0

    prioridad, puntuacion, nombre = min(
        candidatas,
        key=lambda candidata: (candidata[0], -candidata[1]),
    )
    return nombre, puntuacion

def detectar_entidades(texto: str | None) -> dict[str, list[str]]:
    tokens, stems = tokenizar_y_stem(texto)
    stems_mensaje = set(stems)
    temas_detectados = []

    for tema, palabras_clave in reglas['entidades']['tema'].items():
        stems_clave = {
            stemmer.stem(token)
            for palabra in palabras_clave
            for token in normalizar_texto(palabra).split()
        }
        if stems_mensaje & stems_clave:
            temas_detectados.append(tema)

    return {'tema': temas_detectados}

def generar_respuesta(mensaje: str | None) -> str:
    nombre_intencion, _ = detectar_intencion(mensaje)

    if nombre_intencion == 'fallback':
        return reglas['fallback'][0]

    intencion = next(
        intencion
        for intencion in reglas['intenciones']
        if intencion['nombre'] == nombre_intencion
    )
    respuesta = intencion['respuestas'][0]
    return respuesta.format(**reglas['datos_institucionales'])

def iniciar_chatbot() -> None:
    print('Hola, soy DOKi, un chatbot para ayuda a la salud mental\n de estudiantes nivel universidad\n ¿En qué puedo ayudarte?')

    while True:
        texto = input()

        if texto.lower() == 'salir':
            break

        print(generar_respuesta(texto))
        print('¿Puedo ayudarte en otra cosa? \n')

if __name__ == '__main__':
    iniciar_chatbot()