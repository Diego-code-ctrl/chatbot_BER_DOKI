import io
import time

import pytest
from PIL import Image

from modelo.agente import Agente
from modelo.config import MODELOS
from modelo.conocimiento import cargar_conocimiento
from modelo.nlp.clasificador import ClasificadorTexto

HAY_MODELO_TEXTO = (MODELOS / 'intenciones.joblib').exists()
HAY_MODELO_VISUAL = (MODELOS / 'vision_efficientnet_b0.pt').exists()
requiere_texto = pytest.mark.skipif(not HAY_MODELO_TEXTO, reason='falta modelos/intenciones.joblib')


class ImagenFalsa:
    """Clasificador visual determinista: devuelve siempre la misma expresión"""

    def __init__(self, expresion='tristeza', confianza=0.9, falla=False, demora=0.0):
        self.expresion, self.confianza, self.falla, self.demora = expresion, confianza, falla, demora
        self.llamadas = 0

    def __call__(self, imagen):
        self.llamadas += 1
        if self.demora:
            time.sleep(self.demora)
        if self.falla:
            raise RuntimeError('fallo simulado')
        return self.expresion, self.confianza


@pytest.fixture(scope='session')
def conocimiento():
    return cargar_conocimiento()


@pytest.fixture(scope='session')
def texto_real():
    if not HAY_MODELO_TEXTO:
        pytest.skip('falta modelos/intenciones.joblib')
    return ClasificadorTexto.cargar()


@pytest.fixture
def crear_agente(conocimiento, texto_real):
    """Agente con el modelo de texto real y un clasificador visual falso y controlable"""
    def _crear(imagen=None, texto='real'):
        return Agente(conocimiento, texto_real if texto == 'real' else texto, imagen, umbral_visual=0.55, versiones={'texto': 'prueba'})
    return _crear


@pytest.fixture
def imagen_png():
    def _crear(formato='PNG', tamano=(64, 64)):
        b = io.BytesIO()
        Image.new('RGB', tamano, (120, 120, 120)).save(b, formato)
        b.seek(0)
        return b
    return _crear
