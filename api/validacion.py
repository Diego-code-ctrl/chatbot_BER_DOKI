"""Validación de entradas. Se hace aquí aunque la interfaz ya la aplique: cualquiera puede llamar a la API"""
import io
import json

from PIL import Image, UnidentifiedImageError

from .config import Config
from .errores import ErrorApi


def validar_texto(texto, cfg: Config) -> str:
    if not isinstance(texto, str) or not texto.strip():
        raise ErrorApi(400, 'TEXTO_INVALIDO', 'El mensaje no puede estar vacío.')
    if len(texto) > cfg.max_caracteres:
        raise ErrorApi(400, 'TEXTO_MUY_LARGO', f'El mensaje supera los {cfg.max_caracteres} caracteres.')
    return texto.strip()


def validar_imagen(archivo, cfg: Config) -> Image.Image:
    """Verifica tamaño y que el archivo sea realmente JPEG o PNG; la imagen vive solo en memoria"""
    datos = archivo.read(cfg.max_bytes_imagen + 1)
    if len(datos) > cfg.max_bytes_imagen:
        raise ErrorApi(413, 'IMAGEN_MUY_GRANDE', 'La imagen supera el tamaño máximo permitido.')
    try:
        with Image.open(io.BytesIO(datos)) as probe:
            probe.verify()
        imagen = Image.open(io.BytesIO(datos))
        formato = imagen.format
        imagen.load()
    except (UnidentifiedImageError, OSError, ValueError):
        raise ErrorApi(415, 'FORMATO_NO_ADMITIDO', 'El archivo no es una imagen válida.')
    if formato not in cfg.formatos_imagen:
        raise ErrorApi(415, 'FORMATO_NO_ADMITIDO', 'Solo se admiten imágenes JPEG o PNG.')
    return imagen


def leer_estado(crudo) -> dict:
    """La memoria de sesión viaja con cada solicitud; llega como objeto JSON o como cadena JSON"""
    if crudo in (None, ''):
        return {}
    if isinstance(crudo, str):
        try:
            crudo = json.loads(crudo)
        except json.JSONDecodeError:
            raise ErrorApi(400, 'ESTADO_INVALIDO', 'El estado de sesión no es un JSON válido.')
    if not isinstance(crudo, dict):
        raise ErrorApi(400, 'ESTADO_INVALIDO', 'El estado de sesión debe ser un objeto.')
    return crudo


def leer_booleano(valor) -> bool:
    return valor is True or str(valor).strip().lower() in ('1', 'true', 'si', 'sí')
