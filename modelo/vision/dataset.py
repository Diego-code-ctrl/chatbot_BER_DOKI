from sklearn.model_selection import train_test_split
from torch.utils.data import Dataset
from torchvision import transforms
from pathlib import Path
from PIL import Image
import pandas as pd
import hashlib
import torch

RAIZ_DATOS = Path(__file__).with_name('archive')
SEMILLA = 42
TAMANO = 224

# Orden de las clases según el documento; las carpetas del dataset están en inglés
CLASES = ['enojo', 'asco', 'miedo', 'alegría', 'tristeza', 'sorpresa', 'neutral']
CARPETAS = {
    'angry': 'enojo',
    'disgust': 'asco',
    'fear': 'miedo',
    'happy': 'alegría',
    'sad': 'tristeza',
    'surprise': 'sorpresa',
    'neutral': 'neutral',
}

# Normalización de entrada de los modelos preentrenados en ImageNet
MEDIA = (0.485, 0.456, 0.406)
DESVIACION = (0.229, 0.224, 0.225)


def listar_imagenes(raiz: Path | None = None) -> pd.DataFrame:
    """
    La versión de Kaggle trae solo train y test. Train se conserva completo
    y test se divide en dos mitades estratificadas, validación y prueba,
    equivalentes a la prueba pública y privada de FER-2013
    """
    raiz = raiz or RAIZ_DATOS
    filas = [
        {'ruta': str(ruta), 'clase': CARPETAS[carpeta.name], 'origen': origen}
        for origen in ('train', 'test')
        for carpeta in sorted((raiz / origen).iterdir())
        if carpeta.name in CARPETAS
        for ruta in sorted(carpeta.glob('*.jpg'))
    ]
    df = pd.DataFrame(filas)

    df['particion'] = 'entrenamiento'
    prueba = df[df['origen'] == 'test']
    indices_validacion, indices_prueba = train_test_split(
        prueba.index,
        test_size=0.5,
        stratify=prueba['clase'],
        random_state=SEMILLA,
    )
    df.loc[indices_validacion, 'particion'] = 'validacion'
    df.loc[indices_prueba, 'particion'] = 'prueba'

    return df.drop(columns='origen')


def depurar_particiones(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """
    FER-2013 trae imágenes idénticas repartidas entre particiones, lo que
    inflaría la evaluación. Solo se limpian validación y prueba, quitando:
    1) imágenes con etiquetas contradictorias, 2) copias de imágenes que ya
    están en entrenamiento y 3) copias entre validación y prueba. El
    entrenamiento no se modifica
    """
    df = df.copy()
    df['huella'] = [hashlib.md5(Path(ruta).read_bytes()).hexdigest() for ruta in df['ruta']]
    evaluacion = df['particion'] != 'entrenamiento'

    contradictoria = evaluacion & (df.groupby('huella')['clase'].transform('nunique') > 1)

    huellas_entrenamiento = set(df.loc[df['particion'] == 'entrenamiento', 'huella'])
    con_entrenamiento = evaluacion & ~contradictoria & df['huella'].isin(huellas_entrenamiento)

    conservada = ~contradictoria & ~con_entrenamiento
    huellas_validacion = set(df.loc[conservada & (df['particion'] == 'validacion'), 'huella'])
    en_ambas = conservada & (df['particion'] == 'prueba') & df['huella'].isin(huellas_validacion)

    informe = {
        'etiquetas_contradictorias': int(contradictoria.sum()),
        'duplicados_con_entrenamiento': int(con_entrenamiento.sum()),
        'duplicados_entre_validacion_y_prueba': int(en_ambas.sum()),
    }
    limpio = df[~(contradictoria | con_entrenamiento | en_ambas)]
    return limpio.drop(columns='huella').reset_index(drop=True), informe


def transformacion(entrenamiento: bool) -> transforms.Compose:
    """
    Gris a 3 canales, escala a 224 x 224 y normalización de ImageNet.
    El aumento de datos solo se aplica en entrenamiento
    """
    pasos = [transforms.Grayscale(num_output_channels=3)]
    if entrenamiento:
        pasos += [
            transforms.Resize((TAMANO, TAMANO)),
            transforms.RandomHorizontalFlip(),
            transforms.RandomAffine(degrees=10, scale=(0.9, 1.1)),
            transforms.ColorJitter(brightness=0.2),
        ]
    else:
        pasos.append(transforms.Resize((TAMANO, TAMANO)))
    pasos += [transforms.ToTensor(), transforms.Normalize(MEDIA, DESVIACION)]

    return transforms.Compose(pasos)


class DatasetFER(Dataset):
    def __init__(self, df: pd.DataFrame, transformacion: transforms.Compose):
        self.rutas = df['ruta'].tolist()
        self.etiquetas = [CLASES.index(clase) for clase in df['clase']]
        self.transformacion = transformacion

    def __len__(self) -> int:
        return len(self.rutas)

    def __getitem__(self, indice: int) -> tuple[torch.Tensor, int]:
        with Image.open(self.rutas[indice]) as imagen:
            return self.transformacion(imagen), self.etiquetas[indice]


def pesos_por_clase(etiquetas, num_clases: int = len(CLASES)) -> torch.Tensor:
    """Peso inverso a la frecuencia: n / (clases * cuenta de la clase)"""
    cuentas = torch.bincount(torch.as_tensor(list(etiquetas)), minlength=num_clases).float()
    return cuentas.sum() / (num_clases * cuentas)


def tabla_distribucion(df: pd.DataFrame) -> pd.DataFrame:
    tabla = pd.crosstab(df['clase'], df['particion'])
    tabla = tabla.reindex(index=CLASES, columns=['entrenamiento', 'validacion', 'prueba'])
    tabla.loc['Total'] = tabla.sum()
    return tabla
