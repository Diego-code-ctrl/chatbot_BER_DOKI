from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer
from sklearn.model_selection import GridSearchCV, StratifiedKFold, train_test_split
from sklearn.calibration import CalibratedClassifierCV
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import Pipeline
from sklearn.svm import LinearSVC
from preprocesamiento import preprocesar
from pathlib import Path
import numpy as np
import pandas as pd
import chatbot

RUTA_DATASET = Path(__file__).with_name('datos') / 'intenciones.csv'
SEMILLA = 42


def cargar_dataset(ruta: Path | None = None) -> pd.DataFrame:
    return pd.read_csv(ruta or RUTA_DATASET)


def dividir_datos(
    df: pd.DataFrame,
    proporcion_prueba: float = 0.2,
    semilla: int = SEMILLA,
) -> tuple[pd.Series, pd.Series, pd.Series, pd.Series]:
    """Separa entrenamiento y prueba conservando la proporción de cada intención"""
    return train_test_split(
        df['texto'],
        df['intencion'],
        test_size=proporcion_prueba,
        stratify=df['intencion'],
        random_state=semilla,
    )


def crear_vectorizador(
    tipo: str = 'tfidf',
    usar_bigramas: bool = True,
    max_features: int | None = None,
) -> CountVectorizer:
    """
    TF-IDF (principal) o Bag of Words (comparación). Ambos usan el mismo
    preprocesamiento que el chatbot en uso, para que entrenamiento y
    producción vean el mismo texto
    """
    parametros = {
        'tokenizer': preprocesar,
        'preprocessor': None,
        'lowercase': False,
        'token_pattern': None,
        'ngram_range': (1, 2) if usar_bigramas else (1, 1),
        'max_features': max_features,
    }

    if tipo == 'tfidf':
        return TfidfVectorizer(sublinear_tf=True, norm='l2', **parametros)
    if tipo == 'bow':
        return CountVectorizer(**parametros)

    raise ValueError(f'Tipo de representación desconocido: {tipo}')


def vectorizar(
    x_train: pd.Series,
    x_test: pd.Series,
    tipo: str = 'tfidf',
    **opciones,
) -> tuple[CountVectorizer, object, object]:
    """El vocabulario se ajusta solo con entrenamiento; la prueba solo se transforma"""
    vectorizador = crear_vectorizador(tipo, **opciones)
    matriz_train = vectorizador.fit_transform(x_train)
    matriz_test = vectorizador.transform(x_test)
    return vectorizador, matriz_train, matriz_test


def crear_pipeline(algoritmo: str, representacion: str = 'tfidf') -> Pipeline:
    """
    Naive Bayes multinomial o SVM lineal. La SVM se calibra para obtener
    probabilidades, necesarias para el umbral de confianza
    """
    if algoritmo == 'nb':
        clasificador = MultinomialNB()
    elif algoritmo == 'svm':
        clasificador = CalibratedClassifierCV(LinearSVC(), cv=3)
    else:
        raise ValueError(f'Algoritmo desconocido: {algoritmo}')

    return Pipeline([
        ('vec', crear_vectorizador(representacion)),
        ('clf', clasificador),
    ])


def __rejilla(algoritmo: str) -> dict:
    hiperparametro = (
        {'clf__alpha': [0.1, 0.3, 0.5, 1.0]}
        if algoritmo == 'nb'
        else {'clf__estimator__C': [0.1, 1, 10]}
    )
    # El tamaño del vocabulario y los bigramas se ajustan con validación cruzada
    return {
        'vec__ngram_range': [(1, 1), (1, 2)],
        'vec__max_features': [None, 300],
        **hiperparametro,
    }


def buscar_hiperparametros(
    algoritmo: str,
    representacion: str,
    x_train: pd.Series,
    y_train: pd.Series,
) -> GridSearchCV:
    """Validación cruzada estratificada de 5 particiones, solo sobre entrenamiento"""
    busqueda = GridSearchCV(
        crear_pipeline(algoritmo, representacion),
        __rejilla(algoritmo),
        scoring='f1_macro',
        cv=StratifiedKFold(n_splits=5, shuffle=True, random_state=SEMILLA),
    )
    return busqueda.fit(x_train, y_train)


def predecir_con_confianza(modelo: Pipeline, texto: str) -> tuple[str, float]:
    probabilidades = modelo.predict_proba([texto])[0]
    indice = int(np.argmax(probabilidades))
    return str(modelo.classes_[indice]), float(probabilidades[indice])


def es_crisis_por_reglas(texto: str) -> bool:
    return chatbot.detectar_intencion(texto)[0] == 'crisis'


def clasificar_mensaje(
    texto: str,
    modelo: Pipeline,
    umbral: float,
) -> tuple[str, float]:
    """
    Sistema híbrido: la crisis se detecta primero por reglas; el resto lo
    decide el modelo, y bajo el umbral de confianza se pide aclaración
    """
    if es_crisis_por_reglas(texto):
        return 'crisis', 1.0

    intencion, confianza = predecir_con_confianza(modelo, texto)
    if confianza < umbral:
        return 'fallback', confianza
    return intencion, confianza


def predecir_reglas(textos) -> list[str]:
    """Línea base: el chatbot por reglas del Avance 1"""
    return [chatbot.detectar_intencion(texto)[0] for texto in textos]


def elegir_umbral(
    probabilidades: np.ndarray,
    clases: np.ndarray,
    reales,
    precision_objetivo: float = 0.85,
) -> float:
    """
    Menor umbral con el que los mensajes aceptados alcanzan la precisión
    objetivo. Se calcula con predicciones de validación cruzada, no con la prueba
    """
    reales = np.asarray(reales)
    predichos = clases[probabilidades.argmax(axis=1)]
    confianzas = probabilidades.max(axis=1)

    for umbral in np.round(np.arange(0.2, 1.0, 0.05), 2):
        aceptados = confianzas >= umbral
        if aceptados.any() and (predichos[aceptados] == reales[aceptados]).mean() >= precision_objetivo:
            return float(umbral)

    return float(confianzas.max())
