from nltk import SnowballStemmer
from nltk.corpus import stopwords
import unicodedata
import nltk
import re

# Inicialización del stemmer
stemmer = SnowballStemmer('spanish')

# Negaciones que no se eliminan: cambian el sentido ('ya no puedo mas')
NEGACIONES = {'no', 'ni', 'nunca', 'sin', 'nada'}


def __quitar_acentos(texto: str) -> str:
    """Quita los acentos, conservando la ñ"""
    texto = texto.replace('ñ', '\0')
    texto = unicodedata.normalize('NFD', texto)
    texto = ''.join(
        caracter
        for caracter in texto
        if unicodedata.category(caracter) != 'Mn'
    )
    return texto.replace('\0', 'ñ')


# Stopwords del español normalizadas igual que el texto, sin las negaciones
STOPWORDS = {
    __quitar_acentos(palabra.lower())
    for palabra in stopwords.words('spanish')
} - NEGACIONES


# Verifica que el texto sea válido, no sea nulo o esté vacío
def __texto_valido(texto: str | None) -> bool:
    return texto is not None and bool(re.search(r'\S', texto))


def normalizar_texto(texto: str | None) -> str:
    """
    Normaliza el texto, quitando los carácteres especiales, puntuaciones
    o incluso espacios duplicados, proceso antes de tokenizar
    """
    if not __texto_valido(texto):
        return ''

    texto = __quitar_acentos(texto.lower())
    texto = ''.join(
        caracter
        for caracter in texto
        if caracter.isalnum() or caracter.isspace()
    )

    return ' '.join(texto.split())


def tokenizar(texto: str | None) -> list[str]:
    texto_normalizado = normalizar_texto(texto)
    if not texto_normalizado:
        return []

    return nltk.word_tokenize(texto_normalizado, language='spanish')


def quitar_stopwords(tokens: list[str]) -> list[str]:
    return [token for token in tokens if token not in STOPWORDS]


def aplicar_stemming(tokens: list[str]) -> list[str]:
    return [stemmer.stem(token) for token in tokens]


def tokenizar_y_stem(texto: str | None) -> tuple[list[str], list[str]]:
    """Usado por las reglas: conserva todos los tokens, también las stopwords"""
    tokens = tokenizar(texto)
    return tokens, aplicar_stemming(tokens)


def preprocesar(texto: str | None) -> list[str]:
    """
    Pipeline completo para el clasificador de intenciones: normalización,
    tokenización, eliminación de stopwords y stemming. Se aplica igual a los
    ejemplos de entrenamiento y a los mensajes en uso
    """
    return aplicar_stemming(quitar_stopwords(tokenizar(texto)))
