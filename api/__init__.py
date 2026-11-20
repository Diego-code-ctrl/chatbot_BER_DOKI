"""API REST de DOKi (Flask). Fábrica de la aplicación"""
import re
import time
import uuid

from flask import Flask, g, request
from flask_limiter import ApplicationLimit, Limiter

from .config import Config
from .errores import registrar_manejadores
from .metricas import Metricas
from .registro import crear_registro, registrar
from .servicios import Servicios, cargar_servicios

_SESION_VALIDA = re.compile(r'[0-9a-f]{16,64}')


def clave_frecuencia() -> str:
    """
    Quien llama es el servidor de Streamlit, así que la IP es casi siempre la misma. Se usa el
    identificador aleatorio de la sesión del navegador; si falta, la IP original que reporta Cloudflare.
    """
    sesion = request.headers.get('X-Doki-Sesion', '')
    if _SESION_VALIDA.fullmatch(sesion):
        return f'sesion:{sesion}'
    return f"ip:{request.headers.get('CF-Connecting-IP') or request.remote_addr or 'desconocida'}"


def create_app(cfg: Config | None = None, svc: Servicios | None = None) -> Flask:
    cfg = cfg or Config.desde_entorno()
    app = Flask(__name__)
    app.config['DOKI'] = cfg
    app.config['SERVICIOS'] = svc if svc is not None else cargar_servicios()
    app.config['METRICAS'] = Metricas()
    app.config['MAX_CONTENT_LENGTH'] = cfg.max_bytes_imagen + 64 * 1024  # imagen + campos del formulario
    eventos = crear_registro(cfg.dir_registros, cfg.registro_max_bytes, cfg.registro_copias)

    # Se registra antes que el limitador para que hasta un 429 lleve identificador
    @app.before_request
    def _identificar():
        g.id_solicitud = uuid.uuid4().hex[:12]
        g.inicio = time.perf_counter()
        g.evento = {}

    # Sin CORS a propósito: quien llama es el servidor de Streamlit, no el navegador
    Limiter(
        clave_frecuencia, app=app, storage_uri='memory://',
        default_limits=[cfg.limite_sesion],
        application_limits=[ApplicationLimit(cfg.limite_global, key_function=lambda: 'global')],
    )

    @app.after_request
    def _registrar(respuesta):
        ms = round((time.perf_counter() - g.get('inicio', time.perf_counter())) * 1000, 2)
        evento = {
            **g.get('evento', {}),
            'id': g.get('id_solicitud'), 'ruta': request.path, 'metodo': request.method,
            'codigo': respuesta.status_code, 'ms': ms, 'codigo_error': g.get('codigo_error'),
        }
        if g.get('error_interno'):
            evento['error'] = g.error_interno
        registrar(eventos, evento)
        app.config['METRICAS'].registrar(request.path, respuesta.status_code, ms, evento)
        respuesta.headers['X-Request-Id'] = g.get('id_solicitud', '')
        return respuesta

    from .rutas import bp
    app.register_blueprint(bp)
    registrar_manejadores(app)
    return app
