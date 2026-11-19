"""
Sustituto local de la API para poder ver y probar la interfaz sin ella. Devuelve la MISMA forma que
/api/v1/chat, de modo que conectar la API real no exige tocar la interfaz. No usa modelos: son frases fijas.
"""
import re
import uuid

from cliente_api import ErrorApi, Imagen
from crisis_local import parece_crisis

EMOCIONALES = {'estres_academico', 'ansiedad_examenes', 'sueno'}
PAUSAS = {'mmm', 'mmm no se', 'no se', 'ehh', 'hmm', 'bueno'}
RESPUESTAS = {
    'saludo': ('saludo', 'Hola, soy DOKi. Puedo orientarte sobre estrés, ansiedad, sueño o tiempo de estudio. ¿Qué te gustaría contarme?'),
    'estres_academico': ('estres_academico', 'Suena a que llevas varios días con mucha carga. Es común sentirse así. ¿Qué es lo que más te pesa ahora?'),
    'ansiedad_examenes': ('ansiedad_examenes', 'Los exámenes pueden generar mucha tensión. Podemos pensar juntos cómo llegar con más calma.'),
    'sueno': ('sueno', 'Dormir mal afecta todo lo demás. Cuéntame cómo han sido tus noches últimamente.'),
    'organizacion_tiempo': ('organizacion_tiempo', 'Ordenar los pendientes por fecha y trabajar en bloques cortos suele ayudar. ¿Qué es lo que más se te acumula?'),
    'solicitar_cita': ('solicitar_cita', 'Puedes pedir una cita con una persona de orientación en el servicio de tu escuela. Te explico cómo, si quieres.'),
}
PROTOCOLO = (
    'Lamento que estés pasando por esto. No estás solo/a. Por favor comunícate ahora con la Línea de la Vida '
    '(800 911 2000) o con emergencias (911). Si puedes, busca a una persona de confianza que esté cerca.'
)
FRASE_IMAGEN = 'Por tu expresión, parece que podrías estar algo cansado/a, pero solo tú sabes cómo te sientes.'


def _norm(t: str) -> str:
    t = t.lower().strip()
    for a, b in zip('áéíóú', 'aeiou'):
        t = t.replace(a, b)
    return re.sub(r'[^\w\s]', '', t)


def _intencion(t: str) -> str | None:
    if re.search(r'\b(hola|buenas|buen dia)\b', t):
        return 'saludo'
    if re.search(r'estres|escuela|tarea|carga', t):
        return 'estres_academico'
    if re.search(r'examen|ansied|nervios', t):
        return 'ansiedad_examenes'
    if re.search(r'dormir|sueno|insomnio', t):
        return 'sueno'
    if re.search(r'organiz|tiempo|procrastin|pendientes', t):
        return 'organizacion_tiempo'
    if re.search(r'persona|cita|orientador|psicolog', t):
        return 'solicitar_cita'
    return None


class ClienteDemo:
    def salud(self) -> dict:
        return {'estado': 'demo', 'texto': False, 'imagen': False, 'umbrales': {}, 'versiones': {'demo': '0'}}

    def chat(self, texto: str, estado: dict, imagen: Imagen | None = None, consentimiento: bool = False) -> dict:
        if not texto.strip():
            raise ErrorApi(400, 'TEXTO_INVALIDO', 'El mensaje no puede estar vacío.')
        e = {'intenciones': [], 'aclaraciones': 0, 'esperando_imagen': False, 'ofertas': [], 'crisis_mostrada': False, **estado}
        t = _norm(texto)
        base = {'id_solicitud': uuid.uuid4().hex[:8], 'expresion': None, 'confianza_visual': None, 'version_modelos': {'demo': '0'}}

        if parece_crisis(texto):
            e['crisis_mostrada'] = True
            return {**base, 'respuesta': [{'tipo': 'crisis', 'contenido': PROTOCOLO}], 'intencion': 'crisis',
                    'confianza_texto': 1.0, 'accion': 'crisis', 'estado': e}
        if t in PAUSAS:
            return {**base, 'respuesta': [{'tipo': 'texto', 'contenido': 'Tómate el tiempo que necesites. Cuando quieras seguir, aquí estoy.'}],
                    'intencion': 'fallback', 'confianza_texto': 0.0, 'accion': 'pausa', 'estado': e}

        intencion = _intencion(t)
        if intencion is None:
            e['aclaraciones'] += 1
            return {**base, 'respuesta': [{'tipo': 'texto', 'contenido': 'No estoy seguro de haber entendido. ¿Quieres hablar de alguno de estos temas?'}],
                    'intencion': 'fallback', 'confianza_texto': 0.2, 'accion': 'aclaracion', 'estado': e}

        e['aclaraciones'] = 0
        e['intenciones'] = (e['intenciones'] + [intencion])[-5:]
        segmentos = [{'tipo': 'texto', 'contenido': RESPUESTAS[intencion][1]}]
        if intencion in EMOCIONALES and len(e['intenciones']) >= 3 and all(i in EMOCIONALES for i in e['intenciones'][-3:]) and 'cita' not in e['ofertas']:
            e['ofertas'].append('cita')
            segmentos.append({'tipo': 'oferta', 'contenido': '¿Te gustaría agendar una cita con una persona de orientación? Puede acompañarte mejor.'})
        resp = {**base, 'respuesta': segmentos, 'intencion': intencion, 'confianza_texto': 0.8, 'accion': 'responder', 'estado': e}
        if imagen is not None and consentimiento and intencion in EMOCIONALES:
            resp['respuesta'].append({'tipo': 'imagen', 'contenido': FRASE_IMAGEN})
            resp['expresion'], resp['confianza_visual'] = 'tristeza', 0.7
        return resp
