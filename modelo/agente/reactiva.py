"""
Capa reactiva: reglas de prioridad fija que protegen al estudiante. Se evalúan en orden y la
primera que se cumple decide el turno; si decide, la capa deliberativa no interviene.
  1. Crisis   2. Pausa   3. Consentimiento de imagen   4. Baja confianza
"""
import re
from dataclasses import dataclass

from modelo.nlp.preprocesamiento import normalizar_texto

# Muletillas de duda con letras repetidas: «mmm», «hmmm», «ehhh», «ummm»
_MULETILLA = re.compile(r'(m{2,}|h+m+|e+h+|e+m+|u+m+|a+h+)')


@dataclass(frozen=True)
class Percepcion:
    intencion: str | None        # intención del modelo; None si el modelo de texto no está disponible
    confianza: float | None
    terminos_conocidos: int      # términos del mensaje presentes en el vocabulario TF-IDF
    crisis_reglas: bool
    pausa: bool
    respuesta_corta: bool        # el mensaje entero es un «sí» o un «no» breve
    hay_imagen: bool
    consentimiento: bool


def es_pausa(texto: str, palabras: list[str], max_palabras: int) -> bool:
    """El mensaje completo es una duda corta («mmm», «no sé», «ni idea»)"""
    tokens = re.sub(r'[^\w\s]', ' ', normalizar_texto(texto)).split()
    if not tokens or len(tokens) > max_palabras:
        return False
    return all(t in palabras or _MULETILLA.fullmatch(t) for t in tokens)


def regla_crisis(p: Percepcion, umbral_crisis: float, min_terminos: int) -> bool:
    """
    Regla 1. Se activa si lo detectan las reglas o el clasificador. Para el clasificador se exige:
    - que no sea una duda corta (el modelo etiqueta «mmm no sé» como crisis) ni un «sí» o «no»
      breve («mejor no» se parece a «mejor desaparecer»);
    - al menos `min_terminos` términos conocidos: con uno solo, «¿quién ganó el partido?» sale
      crisis por «gan» (de «ganas de morirme»). En validación cruzada exigir 2 no reduce el recall
      de crisis (24/30 con y sin la condición) y quita falsos positivos.
    Las reglas no tienen esas condiciones: lo que detectan es crisis siempre.
    """
    if p.crisis_reglas:
        return True
    return (
        p.intencion == 'crisis'
        and p.confianza is not None
        and p.confianza >= umbral_crisis
        and p.terminos_conocidos >= min_terminos
        and not p.pausa
        and not p.respuesta_corta
    )


def regla_pausa(p: Percepcion) -> bool:
    """Regla 2 (solo si la 1 no se activó)"""
    return p.pausa


def regla_consentimiento(p: Percepcion) -> bool:
    """Regla 3. Devuelve si se permite ejecutar el clasificador visual"""
    return p.hay_imagen and p.consentimiento


def regla_baja_confianza(p: Percepcion, umbral_texto: float, umbral_sin_vocabulario: float) -> bool:
    """
    Regla 4. Confianza bajo el umbral; o ninguna palabra conocida y confianza bajo un umbral más
    exigente (los n-gramas de caracteres reconocen «estresadisimo» con ~0,64, pero «jajaja» queda
    en ~0,4); o una etiqueta «crisis» que la regla 1 no aceptó: el protocolo nunca va como texto normal.
    """
    return (
        p.confianza is None
        or p.confianza < umbral_texto
        or (p.terminos_conocidos == 0 and p.confianza < umbral_sin_vocabulario)
        or p.intencion == 'crisis'
    )
