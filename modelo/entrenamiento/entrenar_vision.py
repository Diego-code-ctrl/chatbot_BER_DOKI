from torch.utils.data import DataLoader
from pathlib import Path
import argparse
import platform
import json
import time

import torch
import torchvision

import modelo_vision as mv
import vision as vi

RAIZ = Path(__file__).parent
RESULTADOS = RAIZ / 'resultados'
MODELOS = RAIZ / 'modelos'


def crear_cargadores(df, lote: int, trabajadores: int) -> dict[str, DataLoader]:
    cargadores = {}
    for particion in ('entrenamiento', 'validacion', 'prueba'):
        subconjunto = df[df['particion'] == particion]
        dataset = vi.DatasetFER(subconjunto, vi.transformacion(particion == 'entrenamiento'))
        cargadores[particion] = DataLoader(
            dataset,
            batch_size=lote,
            shuffle=particion == 'entrenamiento',
            num_workers=trabajadores,
            persistent_workers=trabajadores > 0,
        )
    return cargadores


def main() -> None:
    argumentos = argparse.ArgumentParser()
    argumentos.add_argument('--arquitectura', default='efficientnet_b0',
                            choices=['efficientnet_b0', 'resnet50', 'cnn_simple'])
    argumentos.add_argument('--lote', type=int, default=64)
    argumentos.add_argument('--lr1', type=float, default=1e-3)
    argumentos.add_argument('--lr2', type=float, default=5e-5)
    argumentos.add_argument('--epocas1', type=int, default=5)
    argumentos.add_argument('--epocas2', type=int, default=10)
    argumentos.add_argument('--paciencia', type=int, default=3)
    argumentos.add_argument('--bloques', type=int, default=3,
                            help='Bloques finales que se descongelan en la fase 2')
    argumentos.add_argument('--limite', type=int, default=0,
                            help='Imágenes por clase y partición (0 = todas); sirve para pruebas rápidas')
    argumentos.add_argument('--trabajadores', type=int, default=4)
    argumentos.add_argument('--sufijo', default='')
    args = argumentos.parse_args()

    RESULTADOS.mkdir(exist_ok=True)
    MODELOS.mkdir(exist_ok=True)
    nombre = args.arquitectura + args.sufijo
    dispositivo = mv.dispositivo_por_defecto()
    torch.manual_seed(vi.SEMILLA)

    df, depuracion = vi.depurar_particiones(vi.listar_imagenes())
    if args.limite:
        df = df.groupby(['particion', 'clase']).head(args.limite).reset_index(drop=True)
    cargadores = crear_cargadores(df, args.lote, args.trabajadores)

    entrenamiento = df[df['particion'] == 'entrenamiento']
    pesos = vi.pesos_por_clase([vi.CLASES.index(c) for c in entrenamiento['clase']])

    preentrenado = args.arquitectura != 'cnn_simple'
    modelo = mv.crear_modelo(args.arquitectura, preentrenado=preentrenado)
    parametros_totales = sum(p.numel() for p in modelo.parameters())

    ruta_modelo = MODELOS / f'vision_{nombre}.pt'
    historial = {'fase': [], 'perdida_entrenamiento': [], 'perdida_validacion': [],
                 'exactitud_entrenamiento': [], 'exactitud_validacion': []}
    inicio = time.time()

    def fase(numero: int, lr: float, epocas: int, congelar_bn: bool) -> None:
        def al_terminar_epoca(epoca, h, mejoro):
            marca = ' *' if mejoro else ''
            print(f'[fase {numero}] época {epoca}/{epocas} '
                  f'pérdida {h["perdida_entrenamiento"][-1]:.4f}/{h["perdida_validacion"][-1]:.4f} '
                  f'exactitud {h["exactitud_entrenamiento"][-1]:.3f}/{h["exactitud_validacion"][-1]:.3f} '
                  f'({time.time() - inicio:.0f} s){marca}', flush=True)
            if mejoro:
                torch.save(modelo.state_dict(), ruta_modelo)

        h = mv.entrenar_fase(
            modelo, cargadores['entrenamiento'], cargadores['validacion'], pesos,
            lr=lr, epocas=epocas, paciencia=args.paciencia, dispositivo=dispositivo,
            congelar_bn=congelar_bn, despues_de_epoca=al_terminar_epoca,
        )
        for clave, valores in h.items():
            historial[clave] += valores
        historial['fase'] += [numero] * len(h['perdida_validacion'])
        torch.save(modelo.state_dict(), ruta_modelo)

    if preentrenado:
        mv.congelar_backbone(modelo)
        fase(1, args.lr1, args.epocas1, congelar_bn=True)
        mv.descongelar_ultimos_bloques(modelo, args.bloques)
        fase(2, args.lr2, args.epocas2, congelar_bn=True)
    else:
        fase(1, args.lr1, args.epocas1 + args.epocas2, congelar_bn=False)

    config = {
        'arquitectura': args.arquitectura,
        'preentrenado_imagenet': preentrenado,
        'parametros_totales': parametros_totales,
        'lote': args.lote,
        'lr_fase_1': args.lr1,
        'lr_fase_2': args.lr2 if preentrenado else None,
        'epocas_maximas_fase_1': args.epocas1 if preentrenado else args.epocas1 + args.epocas2,
        'epocas_maximas_fase_2': args.epocas2 if preentrenado else None,
        'bloques_descongelados': args.bloques if preentrenado else None,
        'paciencia': args.paciencia,
        'optimizador': 'Adam',
        'dropout': 0.3,
        'imagenes_por_clase_y_particion_limite': args.limite or None,
        'imagenes_por_particion': df['particion'].value_counts().to_dict(),
        'depuracion': depuracion,
        'dispositivo': dispositivo,
        'sistema': platform.platform(),
        'python': platform.python_version(),
        'pytorch': torch.__version__,
        'torchvision': torchvision.__version__,
        'semilla': vi.SEMILLA,
        'epocas_entrenadas': len(historial['perdida_validacion']),
        'tiempo_entrenamiento_segundos': round(time.time() - inicio),
    }
    (RESULTADOS / f'vision_{nombre}_config.json').write_text(
        json.dumps(config, indent=2, ensure_ascii=False), encoding='utf-8'
    )
    (RESULTADOS / f'vision_{nombre}_historial.json').write_text(
        json.dumps(historial, indent=2), encoding='utf-8'
    )
    print('Listo:', ruta_modelo, f'({config["tiempo_entrenamiento_segundos"]} s)')


if __name__ == '__main__':
    main()
