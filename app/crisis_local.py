"""
Detección mínima de crisis en la propia interfaz, para cuando la API no responde (plan de mejora,
prioridad alta). No sustituye al agente: solo decide si el aviso de error debe ir acompañado del
protocolo de ayuda. Es deliberadamente amplia: aquí un falso positivo cuesta mucho menos que un falso negativo.
"""
import re
import unicodedata

PATRONES = [
    r'suicid', r'matarme', r'me quiero matar', r'quitarme la vida', r'quitar la vida', r'acabar con (todo|mi vida)',
    r'terminar con todo', r'no quiero (vivir|seguir|despertar|existir)', r'quiero morir', r'morirme',
    r'hacerme dano', r'lastimarme', r'me estoy lastimando', r'cortarme', r'me corto', r'me hago cortes',
    r'desaparecer', r'no (vale|tiene) (la pena|sentido) (vivir|seguir)', r'mejor sin mi', r'ya no (puedo|aguanto) mas',
    r'prefiero no existir', r'harto de vivir', r'harta de vivir',
]
_REGEX = re.compile('|'.join(PATRONES))

PROTOCOLO_LOCAL = (
    'Lo que escribiste me importa. Ahora mismo no puedo responderte como siempre, pero no tienes que '
    'enfrentarlo solo/a: llama a la Línea de la Vida (800 911 2000), disponible las 24 horas, o al 911 si '
    'sientes que corres peligro. Si puedes, busca a una persona de confianza que esté cerca.'
)


def _normalizar(texto: str) -> str:
    texto = unicodedata.normalize('NFKD', texto.lower())
    return ''.join(c for c in texto if not unicodedata.combining(c))


def parece_crisis(texto: str) -> bool:
    return bool(_REGEX.search(_normalizar(texto)))
