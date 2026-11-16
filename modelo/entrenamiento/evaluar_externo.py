"""
Evaluación con mensajes que ningún modelo vio (datos/intenciones_externo.csv) y calibración de la
regla de crisis. Compara el modelo del Avance 2 con el actual al nivel del agente: una aclaración
cuenta como fallo, porque el estudiante no recibe respuesta a su tema.

    python -m modelo.entrenamiento.evaluar_externo
"""
import json

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.model_selection import StratifiedKFold

from modelo.agente import deliberativa, reactiva
from modelo.config import DATOS, MODELOS, RESULTADOS
from modelo.conocimiento import cargar_conocimiento
from modelo.nlp import intenciones as it
from modelo.nlp.clasificador import ClasificadorTexto

UMBRALES_CRISIS = (0.2, 0.25, 0.3, 0.35, 0.4)
MINIMOS_TERMINOS = (1, 2)


def decision_agente(clf: ClasificadorTexto, texto: str, c, umbral_crisis: float, min_terminos: int) -> str:
    """Lo que el agente haría con el mensaje: una intención, 'crisis', 'pausa' o 'aclaracion'"""
    intencion, confianza, terminos = clf.clasificar(texto)
    pausa = reactiva.es_pausa(texto, c['palabras_pausa'], c['max_palabras_pausa'])
    corta = deliberativa.respuesta_corta(texto, c) is not None
    p = reactiva.Percepcion(intencion, confianza, terminos, it.es_crisis_por_reglas(texto), pausa, corta, False, False)
    if reactiva.regla_crisis(p, umbral_crisis, min_terminos):
        return 'crisis'
    if pausa:
        return 'pausa'
    if reactiva.regla_baja_confianza(p, clf.umbral, c['umbral_sin_vocabulario']):
        return 'aclaracion'
    return intencion


def evaluar_externo(c) -> pd.DataFrame:
    externo = pd.read_csv(DATOS / 'intenciones_externo.csv')
    modelos = {'Avance 2': MODELOS / 'intenciones_avance2.joblib', 'Actual': MODELOS / 'intenciones.joblib'}
    filas = []
    for nombre, ruta in modelos.items():
        if not ruta.exists():
            continue
        clf = ClasificadorTexto.cargar(ruta)
        pred = np.array([decision_agente(clf, t, c, c['umbral_crisis'], c['min_terminos_crisis']) for t in externo.texto])
        reales = externo.intencion.values
        conocidas = np.isin(reales, list(clf.pipeline.classes_))
        crisis = reales == 'crisis'
        filas.append({
            'modelo': nombre,
            'mensajes': len(reales),
            'aciertos_agente': round(float((pred == reales).mean()), 4),
            'aciertos_en_intenciones_conocidas': round(float((pred[conocidas] == reales[conocidas]).mean()), 4),
            'aclaraciones': round(float((pred == 'aclaracion').mean()), 4),
            'recall_crisis': round(float((pred[crisis] == 'crisis').mean()), 4),
            'falsos_positivos_crisis': int(((pred == 'crisis') & ~crisis).sum()),
        })
        if nombre == 'Actual':
            pd.DataFrame({'texto': externo.texto, 'real': reales, 'agente': pred}).query('real != agente').to_csv(
                RESULTADOS / 'intenciones_externo_errores.csv', index=False)
    return pd.DataFrame(filas)


def calibrar_crisis(c) -> pd.DataFrame:
    """Recall y falsos positivos de crisis (reglas o clasificador) con validación cruzada sobre todo el corpus"""
    df = it.cargar_dataset()
    x, y = df.texto.to_numpy(dtype=object), df.intencion.to_numpy(dtype=object)
    base = ClasificadorTexto.cargar()
    reglas = np.array([it.es_crisis_por_reglas(t) for t in x])
    pausas = np.array([
        reactiva.es_pausa(t, c['palabras_pausa'], c['max_palabras_pausa']) or deliberativa.respuesta_corta(t, c) is not None
        for t in x
    ])
    prob_crisis, top, terminos = np.zeros(len(x)), np.empty(len(x), dtype=object), np.zeros(len(x), dtype=int)
    for train, test in StratifiedKFold(5, shuffle=True, random_state=it.SEMILLA).split(x, y):
        modelo = clone(base.pipeline).fit(list(x[train]), list(y[train]))
        clf = ClasificadorTexto(modelo, base.umbral)
        probas = modelo.predict_proba(list(x[test]))
        top[test] = modelo.classes_[probas.argmax(axis=1)]
        prob_crisis[test] = probas.max(axis=1)
        terminos[test] = [clf.terminos_conocidos(t) for t in x[test]]
    es_crisis = y == 'crisis'
    filas = []
    for u in UMBRALES_CRISIS:
        for m in MINIMOS_TERMINOS:
            modelo_dice = (top == 'crisis') & (prob_crisis >= u) & (terminos >= m) & ~pausas
            detecta = reglas | modelo_dice
            filas.append({
                'umbral_crisis': u, 'min_terminos': m,
                'recall_combinado': round(float(detecta[es_crisis].mean()), 4),
                'recall_solo_clasificador': round(float(modelo_dice[es_crisis].mean()), 4),
                'falsos_positivos': int((detecta & ~es_crisis).sum()),
                'mensajes_crisis': int(es_crisis.sum()),
            })
    return pd.DataFrame(filas)


def main() -> None:
    c = cargar_conocimiento()
    externo = evaluar_externo(c)
    externo.to_csv(RESULTADOS / 'intenciones_externo.csv', index=False)
    crisis = calibrar_crisis(c)
    crisis.to_csv(RESULTADOS / 'intenciones_crisis_calibracion.csv', index=False)
    print(externo.to_string(index=False))
    print()
    print(crisis.to_string(index=False))
    print('\nParámetros vigentes:', json.dumps({k: c[k] for k in ('umbral_crisis', 'min_terminos_crisis')}))


if __name__ == '__main__':
    main()
