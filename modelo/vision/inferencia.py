"""Carga del clasificador visual para inferencia. La imagen se procesa en memoria y nunca se escribe en disco"""
from pathlib import Path
from typing import Callable

from modelo.config import MODELOS

ClasificadorImagen = Callable[[object], tuple[str, float]]


def crear_clasificador_visual(arquitectura: str = 'efficientnet_b0', ruta: Path | None = None) -> ClasificadorImagen:
    import torch
    from PIL import Image

    from modelo.vision import arquitectura as mv
    from modelo.vision import dataset as vi

    modelo = mv.crear_modelo(arquitectura, preentrenado=False)
    modelo.load_state_dict(torch.load(ruta or MODELOS / f'vision_{arquitectura}.pt', map_location='cpu'))
    modelo.eval()
    transformacion = vi.transformacion(entrenamiento=False)

    def clasificar(entrada) -> tuple[str, float]:
        # Acepta una imagen ya abierta (API) o una ruta (consola)
        if isinstance(entrada, Image.Image):
            tensor = transformacion(entrada.convert('RGB')).unsqueeze(0)
        else:
            with Image.open(entrada) as imagen:
                tensor = transformacion(imagen).unsqueeze(0)
        with torch.no_grad():
            probabilidades = torch.softmax(modelo(tensor), dim=1)[0]
        indice = int(probabilidades.argmax())
        return vi.CLASES[indice], float(probabilidades[indice])

    return clasificar
