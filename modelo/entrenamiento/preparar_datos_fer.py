from pathlib import Path
from PIL import Image
import matplotlib

matplotlib.use('Agg')

import matplotlib.pyplot as plt
import pandas as pd
import hashlib
import json

import vision as vi

RESULTADOS = Path(__file__).with_name('resultados')
MUESTRAS_POR_CLASE = 12


def revisar_imagenes(df: pd.DataFrame) -> dict:
    """Detecta archivos ilegibles, tamaños inesperados y duplicados exactos entre particiones"""
    ilegibles, tamanos_raros, hashes = [], 0, {}
    for ruta, particion in zip(df['ruta'], df['particion']):
        try:
            with Image.open(ruta) as imagen:
                imagen.load()
                if imagen.size != (48, 48):
                    tamanos_raros += 1
        except Exception:
            ilegibles.append(ruta)
            continue
        huella = hashlib.md5(Path(ruta).read_bytes()).hexdigest()
        hashes.setdefault(huella, set()).add(particion)

    duplicados_entre_particiones = sum(1 for particiones in hashes.values() if len(particiones) > 1)
    return {
        'imagenes_ilegibles': len(ilegibles),
        'imagenes_de_tamano_distinto_a_48x48': tamanos_raros,
        'archivos_con_contenido_identico_en_varias_particiones': duplicados_entre_particiones,
    }


def guardar_muestras(df: pd.DataFrame) -> None:
    """Cuadrícula de ejemplos por clase para la revisión manual de calidad"""
    figura, ejes = plt.subplots(
        len(vi.CLASES), MUESTRAS_POR_CLASE, figsize=(MUESTRAS_POR_CLASE * 0.9, len(vi.CLASES) * 1.0)
    )
    entrenamiento = df[df['particion'] == 'entrenamiento']
    for fila, clase in enumerate(vi.CLASES):
        rutas = entrenamiento[entrenamiento['clase'] == clase].sample(
            MUESTRAS_POR_CLASE, random_state=vi.SEMILLA
        )['ruta']
        for columna, ruta in enumerate(rutas):
            eje = ejes[fila][columna]
            eje.imshow(Image.open(ruta), cmap='gray')
            eje.axis('off')
            if columna == 0:
                eje.set_title(clase, fontsize=8, loc='left')
    plt.tight_layout()
    plt.savefig(RESULTADOS / 'fer2013_muestras.png', dpi=130)
    plt.close()


def main() -> None:
    RESULTADOS.mkdir(exist_ok=True)
    df_original = vi.listar_imagenes()
    tabla_original = vi.tabla_distribucion(df_original)
    tabla_original.to_csv(RESULTADOS / 'fer2013_distribucion_original.csv', index_label='clase')

    df, depuracion = vi.depurar_particiones(df_original)
    depuracion['imagenes_antes'] = len(df_original)
    depuracion['imagenes_despues'] = len(df)
    (RESULTADOS / 'fer2013_depuracion.json').write_text(
        json.dumps(depuracion, indent=2), encoding='utf-8'
    )

    tabla = vi.tabla_distribucion(df)
    tabla.to_csv(RESULTADOS / 'fer2013_distribucion.csv', index_label='clase')

    entrenamiento = df[df['particion'] == 'entrenamiento']
    pesos = vi.pesos_por_clase([vi.CLASES.index(c) for c in entrenamiento['clase']])
    pd.DataFrame({'clase': vi.CLASES, 'peso': pesos.numpy().round(3)}).to_csv(
        RESULTADOS / 'fer2013_pesos_clase.csv', index=False
    )

    calidad = revisar_imagenes(df_original)
    (RESULTADOS / 'fer2013_revision_calidad.json').write_text(
        json.dumps(calidad, indent=2), encoding='utf-8'
    )
    guardar_muestras(df)

    print('Depuración:', depuracion)
    print(tabla.to_string())
    print('\nPesos por clase:', dict(zip(vi.CLASES, pesos.numpy().round(2))))
    print('Revisión:', calidad)


if __name__ == '__main__':
    main()
