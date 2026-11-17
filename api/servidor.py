"""Arranque con Waitress (servidor WSGI, un solo proceso con hilos): python -m api.servidor"""
from waitress import serve

from . import create_app
from .config import Config


def main() -> None:
    cfg = Config.desde_entorno()
    if not cfg.clave_api:
        raise SystemExit('Define DOKI_API_KEY antes de iniciar la API.')
    serve(create_app(cfg), host=cfg.host, port=cfg.puerto, threads=cfg.hilos)


if __name__ == '__main__':
    main()
