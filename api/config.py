"""Configuración de la API. Todo valor sensible llega por variables de entorno, nunca del código"""
import os
from dataclasses import dataclass
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Config:
    clave_api: str = ''
    clave_admin: str = ''
    max_caracteres: int = 500
    max_bytes_imagen: int = 5 * 1024 * 1024
    formatos_imagen: tuple[str, ...] = ('JPEG', 'PNG')
    # La API está detrás de Streamlit y del túnel: casi todo llega desde la misma IP. El límite se
    # aplica por sesión del navegador (cabecera X-Doki-Sesion) y, además, uno global protege al equipo.
    limite_sesion: str = '20 per minute'
    limite_global: str = '120 per minute'
    dir_registros: Path | None = RAIZ / 'logs'
    registro_max_bytes: int = 1_000_000
    registro_copias: int = 5
    host: str = '127.0.0.1'
    puerto: int = 8000
    hilos: int = 4

    @classmethod
    def desde_entorno(cls) -> 'Config':
        return cls(
            clave_api=os.getenv('DOKI_API_KEY', ''),
            clave_admin=os.getenv('DOKI_ADMIN_KEY', ''),
            max_caracteres=int(os.getenv('DOKI_MAX_CARACTERES', 500)),
            max_bytes_imagen=int(os.getenv('DOKI_MAX_BYTES_IMAGEN', 5 * 1024 * 1024)),
            limite_sesion=os.getenv('DOKI_LIMITE_SESION', '20 per minute'),
            limite_global=os.getenv('DOKI_LIMITE_GLOBAL', '120 per minute'),
            dir_registros=Path(os.getenv('DOKI_DIR_REGISTROS', RAIZ / 'logs')),
            host=os.getenv('DOKI_API_HOST', '127.0.0.1'),
            puerto=int(os.getenv('DOKI_API_PUERTO', 8000)),
            hilos=int(os.getenv('DOKI_API_HILOS', 4)),
        )
