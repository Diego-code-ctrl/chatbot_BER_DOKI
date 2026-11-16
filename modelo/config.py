"""Rutas compartidas por todo el paquete `modelo`"""
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DATOS = RAIZ / 'datos'
MODELOS = RAIZ / 'modelos'
RESULTADOS = RAIZ / 'resultados'
IMAGENES_FER = RAIZ / 'archive'
REGLAS = Path(__file__).resolve().parent / 'conocimiento' / 'reglas.json'
