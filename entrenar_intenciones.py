from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    precision_recall_fscore_support,
)
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from pathlib import Path
import matplotlib

matplotlib.use('Agg')

import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import joblib
import json

import intenciones as it

RAIZ = Path(__file__).parent
RESULTADOS = RAIZ / 'resultados'
MODELOS = RAIZ / 'modelos'

INTENCIONES = [
    'saludo', 'despedida', 'ayuda_capacidades', 'estres_academico',
    'ansiedad_examenes', 'sueno', 'tecnica_respiracion',
    'organizacion_tiempo', 'solicitar_cita', 'horarios_ubicacion',
    'fuera_de_alcance', 'compartir_imagen', 'crisis',
]
NOMBRES = {
    ('nb', 'tfidf'): 'Naive Bayes + TF-IDF',
    ('nb', 'bow'): 'Naive Bayes + Bag of Words',
    ('svm', 'tfidf'): 'SVM lineal + TF-IDF',
    ('svm', 'bow'): 'SVM lineal + Bag of Words',
}


def metricas(reales, predichos) -> dict:
    """Las predicciones fuera de las 13 intenciones (fallback) cuentan como error"""
    resultado = {'accuracy': accuracy_score(reales, predichos)}
    for promedio in ('macro', 'weighted'):
        p, r, f, _ = precision_recall_fscore_support(
            reales, predichos, labels=INTENCIONES, average=promedio, zero_division=0
        )
        resultado.update({
            f'precision_{promedio}': p,
            f'recall_{promedio}': r,
            f'f1_{promedio}': f,
        })
    return resultado


def recall_crisis(reales, predichos) -> tuple[float, int]:
    reales = list(reales)
    indices = [i for i, real in enumerate(reales) if real == 'crisis']
    aciertos = sum(predichos[i] == 'crisis' for i in indices)
    return aciertos / len(indices), len(indices)


def main() -> None:
    RESULTADOS.mkdir(exist_ok=True)
    MODELOS.mkdir(exist_ok=True)

    df = it.cargar_dataset()
    x_train, x_test, y_train, y_test = it.dividir_datos(df)
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=it.SEMILLA)

    filas = []
    busquedas = {}
    for (algoritmo, representacion), nombre in NOMBRES.items():
        busqueda = it.buscar_hiperparametros(algoritmo, representacion, x_train, y_train)
        busquedas[(algoritmo, representacion)] = busqueda
        filas.append({
            'configuracion': nombre,
            'f1_macro_validacion_cruzada': busqueda.best_score_,
            'mejores_parametros': json.dumps(
                {k: str(v) for k, v in busqueda.best_params_.items()}, ensure_ascii=False
            ),
            **metricas(y_test, busqueda.predict(x_test)),
        })

    reglas_pred = it.predecir_reglas(x_test)
    filas.append({
        'configuracion': 'Reglas del Avance 1 (línea base)',
        **metricas(y_test, reglas_pred),
    })

    # El modelo se elige con la validación cruzada, nunca con la prueba
    elegida = max(busquedas, key=lambda clave: busquedas[clave].best_score_)
    busqueda = busquedas[elegida]
    modelo = busqueda.best_estimator_

    hibrido_pred = [
        'crisis' if it.es_crisis_por_reglas(texto) else prediccion
        for texto, prediccion in zip(x_test, modelo.predict(x_test))
    ]
    filas.append({
        'configuracion': f'Híbrido: {NOMBRES[elegida]} + crisis por reglas',
        **metricas(y_test, hibrido_pred),
    })
    pd.DataFrame(filas).round(4).to_csv(RESULTADOS / 'intenciones_comparacion.csv', index=False)

    # Detalle por intención del modelo elegido
    reporte = classification_report(
        y_test, modelo.predict(x_test), labels=INTENCIONES, output_dict=True, zero_division=0
    )
    por_clase = pd.DataFrame(
        [{'intencion': i, **{k: reporte[i][k] for k in ('precision', 'recall', 'f1-score', 'support')}}
         for i in INTENCIONES]
    )
    por_clase.round(4).to_csv(RESULTADOS / 'intenciones_por_clase.csv', index=False)

    # Matriz de confusión 13 x 13
    matriz = confusion_matrix(y_test, modelo.predict(x_test), labels=INTENCIONES)
    plt.figure(figsize=(11, 9))
    sns.heatmap(matriz, annot=True, fmt='d', cmap='Blues',
                xticklabels=INTENCIONES, yticklabels=INTENCIONES)
    plt.xlabel('Intención predicha')
    plt.ylabel('Intención real')
    plt.title(f'Matriz de confusión: {NOMBRES[elegida]}')
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()
    plt.savefig(RESULTADOS / 'intenciones_confusion.png', dpi=150)
    plt.close()

    # Crisis: error asimétrico, se reporta aparte
    crisis_modelo = recall_crisis(y_test, list(modelo.predict(x_test)))
    crisis_reglas = recall_crisis(y_test, reglas_pred)
    crisis_hibrido = recall_crisis(y_test, hibrido_pred)
    pd.DataFrame([
        {'mecanismo': 'Clasificador', 'recall_crisis': crisis_modelo[0], 'mensajes_crisis': crisis_modelo[1]},
        {'mecanismo': 'Reglas del Avance 1', 'recall_crisis': crisis_reglas[0], 'mensajes_crisis': crisis_reglas[1]},
        {'mecanismo': 'Combinado (reglas o clasificador)', 'recall_crisis': crisis_hibrido[0], 'mensajes_crisis': crisis_hibrido[1]},
    ]).round(4).to_csv(RESULTADOS / 'intenciones_crisis.csv', index=False)

    # Umbral de confianza con validación cruzada sobre entrenamiento
    probas = cross_val_predict(modelo, x_train, y_train, cv=cv, method='predict_proba')
    umbral = it.elegir_umbral(probas, modelo.classes_, y_train)
    predichas_cv = modelo.classes_[probas.argmax(axis=1)]
    confianzas_cv = probas.max(axis=1)
    pd.DataFrame([
        {
            'umbral': u,
            'cobertura': (confianzas_cv >= u).mean(),
            'precision_aceptados': (predichas_cv[confianzas_cv >= u] == y_train.values[confianzas_cv >= u]).mean(),
        }
        for u in (0.2, 0.25, 0.3, 0.35, 0.4, 0.45, 0.5, 0.55, 0.6, 0.65, 0.7)
    ]).round(3).to_csv(RESULTADOS / 'intenciones_umbral_curva.csv', index=False)
    confianzas = modelo.predict_proba(x_test).max(axis=1)
    bajo_umbral = float((confianzas < umbral).mean())
    (RESULTADOS / 'intenciones_umbral.json').write_text(
        json.dumps({
            'modelo': NOMBRES[elegida],
            'umbral': umbral,
            'porcentaje_prueba_bajo_umbral': round(bajo_umbral * 100, 1),
        }, ensure_ascii=False, indent=2),
        encoding='utf-8',
    )

    # Mensajes mal clasificados por el modelo elegido
    pred_modelo = modelo.predict(x_test)
    errores = pd.DataFrame({
        'texto': list(x_test),
        'real': list(y_test),
        'predicha': pred_modelo,
        'confianza': confianzas.round(3),
    })
    errores[errores['real'] != errores['predicha']].to_csv(
        RESULTADOS / 'intenciones_errores.csv', index=False
    )

    joblib.dump({'modelo': modelo, 'umbral': umbral}, MODELOS / 'intenciones.joblib')

    print(pd.DataFrame(filas).round(3).drop(columns='mejores_parametros').to_string(index=False))
    print('\nElegida:', NOMBRES[elegida], busqueda.best_params_)
    print('Umbral:', umbral, '| prueba bajo umbral:', round(bajo_umbral * 100, 1), '%')
    print('Recall de crisis (clasificador, reglas, combinado):',
          crisis_modelo[0], crisis_reglas[0], crisis_hibrido[0], 'de', crisis_modelo[1])


if __name__ == '__main__':
    main()
