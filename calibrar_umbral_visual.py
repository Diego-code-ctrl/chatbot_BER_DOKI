from torch.utils.data import DataLoader
from pathlib import Path
import pandas as pd
import numpy as np
import argparse
import json

from evaluar_vision import cargar_modelo
import intenciones as it
import modelo_vision as mv
import vision as vi

RESULTADOS = Path(__file__).parent / 'resultados'


def main() -> None:
    argumentos = argparse.ArgumentParser()
    argumentos.add_argument('--precision', type=float, default=0.75)
    args = argumentos.parse_args()

    df, _ = vi.depurar_particiones(vi.listar_imagenes())
    validacion = df[df['particion'] == 'validacion'].reset_index(drop=True)
    datos = DataLoader(
        vi.DatasetFER(validacion, vi.transformacion(entrenamiento=False)),
        batch_size=128, num_workers=4,
    )
    probabilidades, reales = mv.predecir_probabilidades(
        cargar_modelo('efficientnet_b0'), datos, mv.dispositivo_por_defecto()
    )
    predichos = probabilidades.argmax(axis=1)
    confianzas = probabilidades.max(axis=1)

    curva = []
    for umbral in np.round(np.arange(0.3, 1.0, 0.05), 2):
        aceptadas = confianzas >= umbral
        curva.append({
            'umbral': float(umbral),
            'imagenes_aceptadas_pct': round(100 * aceptadas.mean(), 1),
            'precision_de_aceptadas': round(float((predichos[aceptadas] == reales[aceptadas]).mean()), 3)
            if aceptadas.any() else None,
        })
    pd.DataFrame(curva).to_csv(RESULTADOS / 'vision_umbral_curva.csv', index=False)

    umbral = it.elegir_umbral(
        probabilidades, np.arange(len(vi.CLASES)), reales, precision_objetivo=args.precision
    )
    aceptadas = confianzas >= umbral
    resumen = {
        'modelo': 'EfficientNet-B0',
        'conjunto': 'validación',
        'precision_objetivo': args.precision,
        'umbral': umbral,
        'imagenes_aceptadas_pct': round(100 * aceptadas.mean(), 1),
        'precision_de_aceptadas': round(float((predichos[aceptadas] == reales[aceptadas]).mean()), 3),
    }
    (RESULTADOS / 'vision_umbral.json').write_text(
        json.dumps(resumen, indent=2, ensure_ascii=False), encoding='utf-8'
    )
    print(pd.DataFrame(curva).to_string(index=False))
    print(resumen)


if __name__ == '__main__':
    main()
