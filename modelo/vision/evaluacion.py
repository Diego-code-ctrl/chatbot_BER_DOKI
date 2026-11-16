from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    precision_recall_fscore_support,
)
import numpy as np
import pandas as pd

METRICAS = ['accuracy', 'precision_macro', 'recall_macro', 'f1_macro', 'f1_ponderado']


def calcular_metricas(reales, predichos) -> dict[str, float]:
    """Macro trata igual a todas las expresiones; ponderado refleja su frecuencia"""
    precision, recall, f1, _ = precision_recall_fscore_support(
        reales, predichos, average='macro', zero_division=0
    )
    _, _, f1_ponderado, _ = precision_recall_fscore_support(
        reales, predichos, average='weighted', zero_division=0
    )
    return {
        'accuracy': accuracy_score(reales, predichos),
        'precision_macro': precision,
        'recall_macro': recall,
        'f1_macro': f1,
        'f1_ponderado': f1_ponderado,
    }


def tabla_por_clase(reales, predichos, clases: list[str]) -> pd.DataFrame:
    precision, recall, f1, soporte = precision_recall_fscore_support(
        reales, predichos, labels=range(len(clases)), zero_division=0
    )
    return pd.DataFrame({
        'clase': clases,
        'precision': precision,
        'recall': recall,
        'f1': f1,
        'imagenes_de_prueba': soporte,
    })


def matriz_confusion(reales, predichos, num_clases: int) -> np.ndarray:
    """Filas: expresión real. Columnas: expresión predicha"""
    return confusion_matrix(reales, predichos, labels=range(num_clases))


def confusiones_frecuentes(
    matriz: np.ndarray,
    clases: list[str],
    cantidad: int = 5,
) -> list[tuple[str, str, int]]:
    """Pares (real, predicha, cantidad) con más errores, sin contar los aciertos"""
    fuera_de_diagonal = matriz.copy()
    np.fill_diagonal(fuera_de_diagonal, 0)
    orden = np.argsort(fuera_de_diagonal, axis=None)[::-1][:cantidad]
    return [
        (clases[i], clases[j], int(fuera_de_diagonal[i, j]))
        for i, j in (np.unravel_index(indice, fuera_de_diagonal.shape) for indice in orden)
    ]


def tabla_comparacion(
    resultados: dict[str, dict[str, float]],
    no_entrenados: list[str] | None = None,
) -> pd.DataFrame:
    """Métricas en filas y un modelo por columna; los no entrenados se marcan como tales"""
    tabla = pd.DataFrame(resultados).reindex(METRICAS)
    for modelo in no_entrenados or []:
        tabla[modelo] = 'No entrenado'
    return tabla
