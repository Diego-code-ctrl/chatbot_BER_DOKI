"""
Registro de eventos: una línea JSON por solicitud, con rotación por tamaño. Solo metadatos técnicos
(identificador, hora, ruta, código, intención, acción, banderas, latencias, error, versiones).
Nunca el texto de los mensajes, las imágenes, las respuestas, el estado de sesión ni la IP.
"""
import json
import logging
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path

CAMPOS_PERMITIDOS = {
    'id', 'ts', 'ruta', 'metodo', 'codigo', 'ms', 'intencion', 'accion', 'crisis', 'imagen_usada',
    'aclaracion', 'oferta', 'tiempos', 'error', 'version_modelos', 'codigo_error',
}


def crear_registro(directorio: Path | None, max_bytes: int, copias: int) -> logging.Logger:
    logger = logging.getLogger('doki.eventos')
    logger.setLevel(logging.INFO)
    logger.propagate = False
    for h in list(logger.handlers):
        logger.removeHandler(h)
    if directorio is not None:
        directorio.mkdir(parents=True, exist_ok=True)
        manejador = RotatingFileHandler(directorio / 'eventos.jsonl', maxBytes=max_bytes, backupCount=copias, encoding='utf-8')
        manejador.setFormatter(logging.Formatter('%(message)s'))
        logger.addHandler(manejador)
    else:
        logger.addHandler(logging.NullHandler())
    return logger


def registrar(logger: logging.Logger, evento: dict) -> None:
    # Lista blanca: aunque alguien agregue un campo por error, no llega al archivo
    limpio = {k: v for k, v in evento.items() if k in CAMPOS_PERMITIDOS}
    limpio.setdefault('ts', datetime.now(timezone.utc).isoformat(timespec='milliseconds'))
    logger.info(json.dumps(limpio, ensure_ascii=False, default=str))
