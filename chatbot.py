from nltk import re, unicodedata
import nltk

tokenizer = nltk.word_tokenize(None)
stemmer = nltk.StemmerI()

def normalizar_texto(texto: str | None):
    ...

def tokenizar_y_stem(texto: str | None):
    ...

intenciones = [{}]

for intencion in intenciones:
    ...

entidades = []

def detectar_intencion(texto: str | None):
    ...

def detectar_entidades(texto: str | None):
    ...

def generar_respuesta(mensaje: str | None) -> str:
    detectar_intencion()
    detectar_entidades()

    respuesta = ''

    return respuesta

def iniciar_chatbot() -> None:
    ...

if __name__ == '__main__':
    iniciar_chatbot()