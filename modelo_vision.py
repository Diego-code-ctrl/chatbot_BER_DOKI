from torch.utils.data import DataLoader
from torchvision import models
from torch import nn
import numpy as np
import torch
import copy

NUM_CLASES = 7


class CNNSimple(nn.Module):
    """Referencia mínima: CNN pequeña entrenada desde cero, sin transferencia"""

    def __init__(self, dropout: float = 0.3):
        super().__init__()
        canales = [3, 16, 32, 64, 128]
        capas = []
        for entrada, salida in zip(canales[:-1], canales[1:]):
            capas += [
                nn.Conv2d(entrada, salida, kernel_size=3, padding=1),
                nn.BatchNorm2d(salida),
                nn.ReLU(),
                nn.MaxPool2d(2),
            ]
        self.features = nn.Sequential(*capas)
        self.pool = nn.AdaptiveAvgPool2d(1)
        self.classifier = nn.Sequential(nn.Dropout(dropout), nn.Linear(canales[-1], NUM_CLASES))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.classifier(torch.flatten(self.pool(self.features(x)), 1))


def crear_modelo(arquitectura: str, preentrenado: bool = True, dropout: float = 0.3) -> nn.Module:
    """
    Cabeza nueva: promedio global (ya incluido en la red), dropout y capa densa
    de 7 salidas. La softmax se aplica al predecir; el entrenamiento usa
    entropía cruzada sobre los logits, que equivale a softmax + log-verosimilitud
    """
    if arquitectura == 'efficientnet_b0':
        pesos = models.EfficientNet_B0_Weights.IMAGENET1K_V1 if preentrenado else None
        modelo = models.efficientnet_b0(weights=pesos)
        modelo.classifier = nn.Sequential(
            nn.Dropout(dropout), nn.Linear(modelo.classifier[1].in_features, NUM_CLASES)
        )
    elif arquitectura == 'resnet50':
        pesos = models.ResNet50_Weights.IMAGENET1K_V1 if preentrenado else None
        modelo = models.resnet50(weights=pesos)
        modelo.fc = nn.Sequential(nn.Dropout(dropout), nn.Linear(modelo.fc.in_features, NUM_CLASES))
    elif arquitectura == 'cnn_simple':
        modelo = CNNSimple(dropout)
    else:
        raise ValueError(f'Arquitectura desconocida: {arquitectura}')

    return modelo


def cabeza(modelo: nn.Module) -> nn.Module:
    return modelo.fc if hasattr(modelo, 'fc') else modelo.classifier


def bloques(modelo: nn.Module) -> list[nn.Module]:
    """Bloques del extractor de características, de la entrada hacia la salida"""
    if hasattr(modelo, 'fc'):
        return [modelo.layer1, modelo.layer2, modelo.layer3, modelo.layer4]
    return list(modelo.features)


def congelar_backbone(modelo: nn.Module) -> None:
    """Fase 1: solo la cabeza nueva se entrena"""
    for parametro in modelo.parameters():
        parametro.requires_grad = False
    for parametro in cabeza(modelo).parameters():
        parametro.requires_grad = True


def descongelar_ultimos_bloques(modelo: nn.Module, cantidad: int) -> None:
    """Fase 2: se liberan los últimos bloques, excepto las capas de normalización por lotes"""
    for bloque in bloques(modelo)[-cantidad:]:
        for modulo in bloque.modules():
            if isinstance(modulo, nn.modules.batchnorm._BatchNorm):
                continue
            for parametro in modulo.parameters(recurse=False):
                parametro.requires_grad = True


def poner_en_entrenamiento(modelo: nn.Module, congelar_bn: bool = True) -> None:
    """Modo entrenamiento; la normalización por lotes queda en evaluación para no alterar sus estadísticas"""
    modelo.train()
    if congelar_bn:
        for modulo in modelo.modules():
            if isinstance(modulo, nn.modules.batchnorm._BatchNorm):
                modulo.eval()


class ParadaAnticipada:
    """Indica cuándo parar: la pérdida de validación lleva `paciencia` épocas sin mejorar"""

    def __init__(self, paciencia: int):
        self.paciencia = paciencia
        self.mejor = float('inf')
        self.sin_mejora = 0
        self.mejoro = False

    def actualizar(self, perdida: float) -> bool:
        self.mejoro = perdida < self.mejor
        if self.mejoro:
            self.mejor = perdida
            self.sin_mejora = 0
        else:
            self.sin_mejora += 1
        return self.sin_mejora >= self.paciencia


def dispositivo_por_defecto() -> str:
    if torch.backends.mps.is_available():
        return 'mps'
    if torch.cuda.is_available():
        return 'cuda'
    return 'cpu'


def evaluar_perdida(
    modelo: nn.Module,
    datos: DataLoader,
    pesos: torch.Tensor,
    dispositivo: str = 'cpu',
) -> tuple[float, float]:
    """Pérdida ponderada por clase y exactitud sobre un conjunto"""
    modelo.eval()
    pesos = pesos.to(dispositivo)
    criterio = nn.CrossEntropyLoss(weight=pesos, reduction='sum')
    perdida, peso_total, aciertos, total = 0.0, 0.0, 0, 0
    with torch.no_grad():
        for imagenes, etiquetas in datos:
            imagenes, etiquetas = imagenes.to(dispositivo), etiquetas.to(dispositivo)
            logits = modelo(imagenes)
            perdida += criterio(logits, etiquetas).item()
            peso_total += pesos[etiquetas].sum().item()
            aciertos += (logits.argmax(dim=1) == etiquetas).sum().item()
            total += len(etiquetas)
    return perdida / peso_total, aciertos / total


def entrenar_fase(
    modelo: nn.Module,
    datos_entrenamiento: DataLoader,
    datos_validacion: DataLoader,
    pesos: torch.Tensor,
    lr: float,
    epocas: int,
    paciencia: int,
    dispositivo: str = 'cpu',
    congelar_bn: bool = True,
    despues_de_epoca=None,
) -> dict[str, list[float]]:
    """
    Entropía cruzada con pesos por clase, parada anticipada por pérdida de
    validación y restauración del mejor modelo (no el último)
    """
    modelo.to(dispositivo)
    pesos_dispositivo = pesos.to(dispositivo)
    criterio = nn.CrossEntropyLoss(weight=pesos_dispositivo, reduction='sum')
    optimizador = torch.optim.Adam(
        [p for p in modelo.parameters() if p.requires_grad], lr=lr
    )
    parada = ParadaAnticipada(paciencia)
    mejor_estado = copy.deepcopy(modelo.state_dict())
    historial = {
        'perdida_entrenamiento': [], 'perdida_validacion': [],
        'exactitud_entrenamiento': [], 'exactitud_validacion': [],
    }

    for epoca in range(1, epocas + 1):
        poner_en_entrenamiento(modelo, congelar_bn)
        perdida, peso_total, aciertos, total = 0.0, 0.0, 0, 0
        for imagenes, etiquetas in datos_entrenamiento:
            imagenes, etiquetas = imagenes.to(dispositivo), etiquetas.to(dispositivo)
            optimizador.zero_grad()
            logits = modelo(imagenes)
            suma = criterio(logits, etiquetas)
            peso_lote = pesos_dispositivo[etiquetas].sum()
            (suma / peso_lote).backward()
            optimizador.step()

            perdida += suma.item()
            peso_total += peso_lote.item()
            aciertos += (logits.argmax(dim=1) == etiquetas).sum().item()
            total += len(etiquetas)

        perdida_val, exactitud_val = evaluar_perdida(modelo, datos_validacion, pesos, dispositivo)
        historial['perdida_entrenamiento'].append(perdida / peso_total)
        historial['exactitud_entrenamiento'].append(aciertos / total)
        historial['perdida_validacion'].append(perdida_val)
        historial['exactitud_validacion'].append(exactitud_val)

        detener = parada.actualizar(perdida_val)
        if parada.mejoro:
            mejor_estado = copy.deepcopy(modelo.state_dict())
        if despues_de_epoca:
            despues_de_epoca(epoca, historial, parada.mejoro)
        if detener:
            break

    modelo.load_state_dict(mejor_estado)
    return historial


def predecir_probabilidades(
    modelo: nn.Module,
    datos: DataLoader,
    dispositivo: str = 'cpu',
) -> tuple[np.ndarray, np.ndarray]:
    """Probabilidades softmax por imagen y etiquetas reales"""
    modelo.to(dispositivo).eval()
    probabilidades, etiquetas_reales = [], []
    with torch.no_grad():
        for imagenes, etiquetas in datos:
            logits = modelo(imagenes.to(dispositivo))
            probabilidades.append(torch.softmax(logits, dim=1).cpu().numpy())
            etiquetas_reales.append(etiquetas.numpy())
    return np.concatenate(probabilidades), np.concatenate(etiquetas_reales)
