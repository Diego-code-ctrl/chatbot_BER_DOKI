from torch.utils.data import DataLoader
from pathlib import Path
from PIL import Image
import matplotlib

matplotlib.use('Agg')

import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import numpy as np
import torch
import json

import evaluacion_vision as ev
import modelo_vision as mv
import vision as vi

RAIZ = Path(__file__).parent
RESULTADOS = RAIZ / 'resultados'
MODELOS = RAIZ / 'modelos'

NOMBRES = {
    'efficientnet_b0': 'EfficientNet-B0',
    'cnn_simple': 'CNN desde cero (referencia)',
}
PRINCIPAL = 'efficientnet_b0'


def cargar_modelo(arquitectura: str):
    modelo = mv.crear_modelo(arquitectura, preentrenado=False)
    modelo.load_state_dict(torch.load(MODELOS / f'vision_{arquitectura}.pt', map_location='cpu'))
    return modelo


def graficar_curvas() -> None:
    """Pérdida y exactitud por época: la distancia entre ambas curvas muestra el sobreajuste"""
    figura, ejes = plt.subplots(2, 2, figsize=(11, 7), sharex='col')
    for columna, arquitectura in enumerate(NOMBRES):
        historial = json.loads((RESULTADOS / f'vision_{arquitectura}_historial.json').read_text())
        epocas = range(1, len(historial['perdida_validacion']) + 1)
        for fila, metrica in enumerate(['perdida', 'exactitud']):
            eje = ejes[fila][columna]
            eje.plot(epocas, historial[f'{metrica}_entrenamiento'], label='Entrenamiento')
            eje.plot(epocas, historial[f'{metrica}_validacion'], label='Validación')
            fases = historial['fase']
            if 2 in fases:
                eje.axvline(fases.index(2) + 0.5, color='gray', linestyle='--', linewidth=1)
                if fila == 0:
                    eje.text(fases.index(2) + 0.7, eje.get_ylim()[1] * 0.97, 'ajuste fino', fontsize=8, va='top')
            eje.set_ylabel('Pérdida' if metrica == 'perdida' else 'Exactitud')
            eje.grid(alpha=0.3)
            if fila == 0:
                eje.set_title(NOMBRES[arquitectura])
            if fila == 1:
                eje.set_xlabel('Época')
            if fila == 0 and columna == 0:
                eje.legend()
    plt.tight_layout()
    plt.savefig(RESULTADOS / 'vision_curvas.png', dpi=150)
    plt.close()


def graficar_confusion(matriz: np.ndarray) -> None:
    normalizada = matriz / matriz.sum(axis=1, keepdims=True)
    figura, ejes = plt.subplots(1, 2, figsize=(15, 6))
    for eje, datos, formato, titulo in [
        (ejes[0], matriz, 'd', 'Conteo de imágenes'),
        (ejes[1], normalizada, '.2f', 'Proporción por fila (recall)'),
    ]:
        sns.heatmap(datos, annot=True, fmt=formato, cmap='Blues', ax=eje,
                    xticklabels=vi.CLASES, yticklabels=vi.CLASES, cbar=False)
        eje.set_xlabel('Expresión predicha')
        eje.set_ylabel('Expresión real')
        eje.set_title(titulo)
    figura.suptitle(f'Matriz de confusión en prueba: {NOMBRES[PRINCIPAL]}')
    plt.tight_layout()
    plt.savefig(RESULTADOS / 'vision_confusion.png', dpi=150)
    plt.close()


def guardar_errores(df_prueba: pd.DataFrame, predichos: np.ndarray, confianzas: np.ndarray) -> None:
    errores = df_prueba.assign(
        predicha=[vi.CLASES[i] for i in predichos],
        confianza=confianzas.round(3),
    ).rename(columns={'clase': 'real'})
    errores = errores[errores['real'] != errores['predicha']].sort_values('confianza', ascending=False)
    errores[['ruta', 'real', 'predicha', 'confianza']].to_csv(
        RESULTADOS / 'vision_errores.csv', index=False
    )

    # Los errores más confiados son los más reveladores: ¿falla el modelo o la etiqueta?
    figura, ejes = plt.subplots(3, 6, figsize=(12, 6.5))
    for eje, (_, fila) in zip(ejes.flat, errores.head(18).iterrows()):
        eje.imshow(Image.open(fila['ruta']), cmap='gray')
        eje.set_title(f'real: {fila["real"]}\npred: {fila["predicha"]} ({fila["confianza"]:.2f})', fontsize=8)
        eje.axis('off')
    figura.suptitle('Errores con mayor confianza del modelo (prueba)')
    plt.tight_layout()
    plt.savefig(RESULTADOS / 'vision_errores.png', dpi=140)
    plt.close()


def main() -> None:
    dispositivo = mv.dispositivo_por_defecto()
    df, _ = vi.depurar_particiones(vi.listar_imagenes())
    df_prueba = df[df['particion'] == 'prueba'].reset_index(drop=True)
    datos = DataLoader(
        vi.DatasetFER(df_prueba, vi.transformacion(entrenamiento=False)),
        batch_size=128, num_workers=4,
    )

    metricas, predicciones = {}, {}
    for arquitectura, nombre in NOMBRES.items():
        probabilidades, reales = mv.predecir_probabilidades(cargar_modelo(arquitectura), datos, dispositivo)
        predichos = probabilidades.argmax(axis=1)
        metricas[nombre] = ev.calcular_metricas(reales, predichos)
        predicciones[arquitectura] = (probabilidades, predichos, reales)

    comparacion = ev.tabla_comparacion(metricas, no_entrenados=['ResNet50 (si se entrena)'])
    comparacion = comparacion[[NOMBRES['efficientnet_b0'], 'ResNet50 (si se entrena)', NOMBRES['cnn_simple']]]
    comparacion.round(4).to_csv(RESULTADOS / 'vision_metricas.csv', index_label='metrica')

    probabilidades, predichos, reales = predicciones[PRINCIPAL]
    por_clase = ev.tabla_por_clase(reales, predichos, vi.CLASES)
    por_clase.round(4).to_csv(RESULTADOS / 'vision_por_clase.csv', index=False)

    matriz = ev.matriz_confusion(reales, predichos, len(vi.CLASES))
    pd.DataFrame(matriz, index=vi.CLASES, columns=vi.CLASES).to_csv(
        RESULTADOS / 'vision_confusion.csv', index_label='real_vs_predicha'
    )
    graficar_confusion(matriz)

    top = ev.confusiones_frecuentes(matriz, vi.CLASES, cantidad=8)
    pd.DataFrame(top, columns=['real', 'predicha', 'imagenes']).to_csv(
        RESULTADOS / 'vision_confusiones_frecuentes.csv', index=False
    )

    guardar_errores(df_prueba, predichos, probabilidades.max(axis=1))
    graficar_curvas()

    print(comparacion.to_string())
    print('\n', por_clase.round(3).to_string(index=False))
    print('\nConfusiones más frecuentes:', top)
    print('Pruebas:', len(df_prueba))


if __name__ == '__main__':
    main()
