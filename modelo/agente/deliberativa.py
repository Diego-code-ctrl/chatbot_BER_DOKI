"""
Capa deliberativa: cuando ninguna regla reactiva decide, consulta la memoria y elige qué añadir
a la respuesta de la intención. Metas, en orden: resolver, canalizar, ofrecer un recurso sin
insistir y mantener la conversación comprensible. Los números son parámetros de diseño de reglas.json.
"""
import re

from modelo.agente.estado import EstadoSesion
from modelo.conocimiento import Conocimiento
from modelo.nlp.preprocesamiento import normalizar_para_caracteres

# Ofertas de la capa deliberativa y la intención que las cumple
OFERTA_A_INTENCION = {'cita': 'solicitar_cita', 'respiracion': 'tecnica_respiracion'}
INTENCION_A_OFERTA = {v: k for k, v in OFERTA_A_INTENCION.items()}


def respuesta_corta(texto: str, c: Conocimiento) -> str | None:
    """
    'si' o 'no' cuando el mensaje entero es una aceptación o un rechazo breve («sí, porfa», «ok»,
    «no gracias», «ahorita no»); None en cualquier otro caso. El texto se compara palabra por palabra.
    """
    tokens = re.sub(r'[^\w\s]', ' ', normalizar_para_caracteres(texto)).split()
    if not tokens or len(tokens) > c['max_palabras_respuesta_corta']:
        return None
    afirmaciones, negaciones = set(c['afirmaciones']), set(c['negaciones'])
    permitidas = afirmaciones | negaciones | set(c['palabras_de_relleno'])
    if not all(t in permitidas for t in tokens):
        return None
    if any(t in negaciones for t in tokens):
        return 'no'
    if any(t in afirmaciones for t in tokens):
        return 'si'
    return None


def elegir_oferta(intencion: str, estado: EstadoSesion, c: Conocimiento) -> str | None:
    """
    Una oferta por turno como máximo, y ninguna se repite en la sesión. Canalizar a una persona
    tiene prioridad y se ofrece siempre que toca; un recurso (respiración) solo se ofrece si la
    respuesta no termina ya con su propia pregunta: dos preguntas juntas vuelven ambiguo un «sí».
    """
    n = c['mensajes_para_canalizar']
    recientes = estado.intenciones[-n:]
    if (
        'cita' not in estado.ofertas
        and len(recientes) == n
        and all(i in c['intenciones_emocionales'] for i in recientes)
    ):
        return 'cita'
    if (
        'respiracion' not in estado.ofertas
        and intencion in c['intenciones_con_respiracion']
        and not c.seguimiento(intencion)
    ):
        return 'respiracion'
    return None


def registrar_ofertas_implicitas(intencion: str, estado: EstadoSesion, c: Conocimiento) -> None:
    """
    Si el estudiante ya pidió la cita o la técnica, o la propia respuesta la ofrece al final,
    ofrecerla de nuevo en este turno o después sería repetirse
    """
    for candidata in (intencion, c.seguimiento(intencion)):
        if candidata in INTENCION_A_OFERTA:
            estado.ofrecer(INTENCION_A_OFERTA[candidata])


def texto_aclaracion(estado: EstadoSesion, c: Conocimiento) -> str:
    """Tras varias aclaraciones seguidas no se repite la pregunta: se dan los temas y la opción de una persona"""
    if estado.aclaraciones >= c['aclaraciones_para_lista']:
        return c.texto('aclaracion_repetida')
    return c.texto('aclaracion')


def acompanamiento(estado: EstadoSesion, c: Conocimiento) -> dict | None:
    """Tras una crisis, cada respuesta de la sesión lleva antes, breve, los recursos de ayuda"""
    if estado.crisis_mostrada:
        return {'tipo': 'recursos', 'contenido': c.texto('recordatorio_post_crisis')}
    return None
