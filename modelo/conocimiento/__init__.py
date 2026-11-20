"""Base de conocimiento: respuestas, plantillas, parámetros del agente y datos institucionales (reglas.json)"""
import json
from functools import lru_cache
from pathlib import Path

from modelo.config import REGLAS


class Conocimiento:
    def __init__(self, datos: dict):
        self.datos = datos
        self.version = str(datos.get('version', '0'))
        self.institucional = datos['datos_institucionales']
        self.agente = datos['agente']
        self.vision = datos['vision']
        self._respuestas = {i['nombre']: i['respuestas'] for i in datos['intenciones']}
        self._seguimiento = {i['nombre']: i['seguimiento'] for i in datos['intenciones'] if i.get('seguimiento')}
        self.intenciones = frozenset(self._respuestas)

    def _formatear(self, plantilla: str, **extra) -> str:
        return plantilla.format(**self.institucional, **extra)

    def respuesta(self, intencion: str, variante: int = 0) -> str:
        """Las variantes rotan para no repetir el mismo párrafo cuando el tema vuelve"""
        variantes = self._respuestas.get(intencion)
        if not variantes:
            return self.texto('aclaracion')
        return self._formatear(variantes[variante % len(variantes)])

    def seguimiento(self, intencion: str) -> str | None:
        """Intención que la respuesta ofrece al final («¿Quieres que te enseñe…?»), si la hay"""
        return self._seguimiento.get(intencion)

    def texto(self, clave: str, **extra) -> str:
        return self._formatear(self.agente['textos'][clave], **extra)

    def frase_visual(self, expresion: str) -> str | None:
        return self.vision['frases'].get(expresion)

    def __getitem__(self, parametro: str):
        return self.agente[parametro]


@lru_cache(maxsize=4)
def cargar_conocimiento(ruta: Path = REGLAS) -> Conocimiento:
    with Path(ruta).open(encoding='utf-8') as archivo:
        return Conocimiento(json.load(archivo))
