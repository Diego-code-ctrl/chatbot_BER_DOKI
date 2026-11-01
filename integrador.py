from pathlib import Path
from typing import Callable
import json
import joblib

import chatbot
import intenciones

RAIZ = Path(__file__).parent
CONFIG_VISION = chatbot.reglas['vision']


class Integrador:
    """
    Coordina el clasificador de texto y el visual en cada turno. La imagen
    complementa al texto y nunca lo sustituye ni activa el protocolo de crisis.
    El único estado que conserva entre turnos es si espera una imagen; la ruta
    y la imagen no se guardan
    """

    def __init__(
        self,
        modelo_texto,
        umbral_texto: float,
        clasificar_imagen: Callable[[str], tuple[str, float]],
        umbral_visual: float,
    ):
        self.modelo_texto = modelo_texto
        self.umbral_texto = umbral_texto
        self.clasificar_imagen = clasificar_imagen
        self.umbral_visual = umbral_visual
        self.esperando_imagen = False

    def turno(self, texto: str, ruta_imagen: str | None = None, autoriza: bool = False) -> str:
        if self.esperando_imagen and ruta_imagen is None and Path(texto.strip()).is_file():
            self.esperando_imagen = False
            return self._comentario_visual(texto.strip(), autoriza) or ''

        self.esperando_imagen = False
        intencion, _ = intenciones.clasificar_mensaje(texto, self.modelo_texto, self.umbral_texto)
        respuesta = chatbot.respuesta_de_intencion(intencion)

        if intencion == 'compartir_imagen':
            self.esperando_imagen = True
        if intencion in ('crisis', 'compartir_imagen') or ruta_imagen is None:
            return respuesta

        comentario = self._comentario_visual(
            ruta_imagen, autoriza, solo_si_aplica_a=intencion
        )
        return f'{respuesta}\n{comentario}' if comentario else respuesta

    def _comentario_visual(
        self,
        ruta: str,
        autoriza: bool,
        solo_si_aplica_a: str | None = None,
    ) -> str | None:
        if not autoriza:
            return CONFIG_VISION['aviso_sin_consentimiento']
        if not Path(ruta).is_file():
            return CONFIG_VISION['aviso_archivo_no_encontrado']

        expresion, confianza = self.clasificar_imagen(ruta)
        if confianza < self.umbral_visual:
            return CONFIG_VISION['aviso_baja_confianza']
        if solo_si_aplica_a and solo_si_aplica_a not in CONFIG_VISION['intenciones_con_frase']:
            return None
        return CONFIG_VISION['frases'][expresion]


def crear_clasificador_visual(arquitectura: str = 'efficientnet_b0') -> Callable[[str], tuple[str, float]]:
    """Carga el modelo entrenado; la imagen se procesa en memoria y no se escribe en disco"""
    import torch
    from PIL import Image
    import modelo_vision as mv
    import vision as vi

    modelo = mv.crear_modelo(arquitectura, preentrenado=False)
    modelo.load_state_dict(torch.load(RAIZ / 'modelos' / f'vision_{arquitectura}.pt', map_location='cpu'))
    modelo.eval()
    transformacion = vi.transformacion(entrenamiento=False)

    def clasificar(ruta: str) -> tuple[str, float]:
        with Image.open(ruta) as imagen:
            tensor = transformacion(imagen).unsqueeze(0)
        with torch.no_grad():
            probabilidades = torch.softmax(modelo(tensor), dim=1)[0]
        indice = int(probabilidades.argmax())
        return vi.CLASES[indice], float(probabilidades[indice])

    return clasificar


def crear_integrador() -> Integrador:
    texto = joblib.load(RAIZ / 'modelos' / 'intenciones.joblib')
    umbral_visual = json.loads((RAIZ / 'resultados' / 'vision_umbral.json').read_text())['umbral']
    return Integrador(texto['modelo'], texto['umbral'], crear_clasificador_visual(), umbral_visual)
