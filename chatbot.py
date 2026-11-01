from preprocesamiento import normalizar_texto, tokenizar_y_stem, stemmer
from pathlib import Path
import json

# Importa las relgas desde el json
ruta_reglas = Path(__file__).with_name('reglas.json')
reglas = None

# Crea un diccionario con las reglas del json para no modificar el código
with ruta_reglas.open(encoding='utf-8') as archivo:
    reglas = json.load(archivo)

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

def respuesta_de_intencion(nombre_intencion: str) -> str:
    if nombre_intencion == 'fallback':
        return reglas['fallback'][0]

    intencion = next(
        intencion
        for intencion in reglas['intenciones']
        if intencion['nombre'] == nombre_intencion
    )
    respuesta = intencion['respuestas'][0]
    return respuesta.format(**reglas['datos_institucionales'])

def generar_respuesta(mensaje: str | None) -> str:
    nombre_intencion, _ = detectar_intencion(mensaje)
    return respuesta_de_intencion(nombre_intencion)

def iniciar_chatbot() -> None:
    from integrador import crear_integrador

    integrador = crear_integrador()
    print('Hola, soy DOKi, un chatbot para ayuda a la salud mental\n de estudiantes nivel universidad\n ¿En qué puedo ayudarte?')

    while True:
        texto = input()

        if texto.lower() == 'salir':
            break

        autoriza = False
        if integrador.esperando_imagen and Path(texto.strip()).is_file():
            autoriza = input('¿Autorizas el uso de esta imagen solo para esta conversación? (sí/no) ').strip().lower() in ('si', 'sí')

        print(integrador.turno(texto, autoriza=autoriza))
        print('¿Puedo ayudarte en otra cosa? \n')

if __name__ == '__main__':
    iniciar_chatbot()