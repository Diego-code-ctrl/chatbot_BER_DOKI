from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer
from sklearn.model_selection import train_test_split
from preprocesamiento import preprocesar
from pathlib import Path
import pandas as pd

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
