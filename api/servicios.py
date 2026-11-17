"""
Puente entre la API y el paquete `modelo`. La API nunca interpreta texto ni imágenes: delega en el
agente. Los modelos se cargan una sola vez al arrancar; si falla el de texto, /salud responde 503,
pero /chat sigue atendiendo con las reglas de crisis (degradación segura).
"""
from dataclasses import dataclass, field

from modelo.agente import Agente


@dataclass
class Servicios:
    agente: Agente
    errores_carga: dict = field(default_factory=dict)

    @property
    def texto_listo(self) -> bool:
        return self.agente.texto is not None

    @property
    def imagen_lista(self) -> bool:
        return self.agente.imagen is not None

    @property
    def listo(self) -> bool:
        return self.texto_listo

    def estado(self) -> dict:
        return {
            'modelos': {'texto': self.texto_listo, 'imagen': self.imagen_lista},
            'umbrales': {
                'texto': self.agente.texto.umbral if self.texto_listo else None,
                'crisis': self.agente.c['umbral_crisis'],
                'imagen': self.agente.umbral_visual,
            },
            'version_modelos': self.agente.versiones,
        }


def cargar_servicios() -> Servicios:
    from modelo.agente import crear_agente
    agente, errores = crear_agente()
    return Servicios(agente, errores)


def clasificar_texto(s: Servicios, texto: str) -> dict:
    p, eventos = s.agente.percibir(texto)
    if p.intencion is None:
        raise RuntimeError(eventos['error'])
    crisis = s.agente.es_crisis(p)
    return {
        'intencion': 'crisis' if crisis else p.intencion,
        'confianza': round(float(1.0 if crisis and p.crisis_reglas else p.confianza), 4),
        'crisis': crisis,
        'bajo_umbral': (p.confianza or 0) < s.agente.texto.umbral,
    }


def clasificar_imagen(s: Servicios, imagen) -> dict:
    expresion, confianza = s.agente.clasificar_imagen(imagen)
    return {
        'expresion': expresion,
        'confianza': round(float(confianza), 4),
        'supera_umbral': confianza >= s.agente.umbral_visual,
    }
