"""Configuración de la interfaz. La dirección de la API y la clave salen de los secretos o del entorno, nunca del código"""
import os
from dataclasses import dataclass

import streamlit as st

MAX_CARACTERES = 500
MAX_BYTES_IMAGEN = 5 * 1024 * 1024
FORMATOS_IMAGEN = ('image/jpeg', 'image/png')
TIMEOUT_CONEXION = 5
TIMEOUT_RESPUESTA = 30

# Ritmo de la escritura progresiva (segundos): ~8 palabras por segundo, con pausa leve tras la puntuación
PAUSA_PALABRA = 0.11
PAUSA_PUNTUACION = 0.30

# Siempre visibles, incluso si la API falla: la ayuda no depende del modelo
LINEA_DE_LA_VIDA = ('Línea de la Vida', '800 911 2000')
EMERGENCIAS = ('Emergencias', '911')

TEMAS_RAPIDOS = [
    'Estrés por la escuela',
    'Ansiedad antes de un examen',
    'No puedo dormir',
    'Organizar mi tiempo',
    'Me siento triste',
    'Quiero hablar con una persona',
]

# Respuestas rápidas cuando DOKi acaba de ofrecer algo («¿Quieres que te enseñe…?»)
RESPUESTAS_OFERTA = ['Sí, por favor', 'No, gracias']


@dataclass(frozen=True)
class Ajustes:
    api_url: str
    api_key: str

    @property
    def modo_demo(self) -> bool:
        return not self.api_url


def _secreto(nombre: str) -> str:
    try:
        return str(st.secrets[nombre])
    except Exception:  # noqa: BLE001  (sin archivo de secretos o sin esa clave)
        return os.getenv(f'DOKI_{nombre}', '')


def cargar_ajustes() -> Ajustes:
    return Ajustes(api_url=_secreto('API_URL').rstrip('/'), api_key=_secreto('API_KEY'))
