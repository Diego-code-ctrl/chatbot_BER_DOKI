"""Rutas /api/v1. La API valida, autentica y delega en el agente; no interpreta texto ni imágenes"""
import hmac

from flask import Blueprint, current_app, g, jsonify, request

from . import servicios, validacion
from .errores import ErrorApi

bp = Blueprint('v1', __name__, url_prefix='/api/v1')
RUTAS_SIN_CLAVE_API = {'v1.salud', 'v1.metricas'}  # /metricas usa su propia clave de administración


def _cfg():
    return current_app.config['DOKI']


def _svc() -> servicios.Servicios:
    return current_app.config['SERVICIOS']


def _clave_valida(recibida: str, esperada: str) -> bool:
    return bool(esperada) and hmac.compare_digest(recibida.encode(), esperada.encode())


@bp.before_request
def _autenticar():
    if request.endpoint in RUTAS_SIN_CLAVE_API:
        return
    if not _clave_valida(request.headers.get('X-API-Key', ''), _cfg().clave_api):
        raise ErrorApi(401, 'NO_AUTORIZADO', 'Servicio no disponible.')


@bp.get('/salud')
def salud():
    """Abierta para que la interfaz detecte el servicio caído antes de que el estudiante escriba"""
    s = _svc()
    cuerpo = {'estado': 'listo' if s.listo else 'no_listo', **s.estado()}
    return jsonify(cuerpo), (200 if s.listo else 503)


@bp.post('/intencion')
def intencion():
    if not _svc().texto_listo:
        raise ErrorApi(503, 'MODELO_NO_CARGADO', 'Servicio no disponible.')
    datos = request.get_json(silent=True) or {}
    texto = validacion.validar_texto(datos.get('texto'), _cfg())
    r = servicios.clasificar_texto(_svc(), texto)
    g.evento = {'intencion': r['intencion'], 'crisis': r['crisis']}
    return jsonify({'id_solicitud': g.id_solicitud, **r})


@bp.post('/imagen')
def imagen():
    if not _svc().imagen_lista:
        raise ErrorApi(503, 'MODELO_NO_CARGADO', 'Servicio no disponible.')
    archivo = request.files.get('imagen')
    if archivo is None:
        raise ErrorApi(400, 'IMAGEN_AUSENTE', 'Falta el campo imagen.')
    img = validacion.validar_imagen(archivo, _cfg())
    try:
        r = servicios.clasificar_imagen(_svc(), img)
    except Exception as e:  # noqa: BLE001
        g.evento = {'error': f'imagen:{type(e).__name__}'}
        raise ErrorApi(503, 'MODELO_NO_DISPONIBLE', 'No se pudo analizar la imagen.')
    g.evento = {'imagen_usada': True}
    return jsonify({'id_solicitud': g.id_solicitud, **r})


@bp.post('/chat')
def chat():
    """Turno completo del agente. Acepta JSON (solo texto) o multipart (con imagen)"""
    cfg = _cfg()
    if request.is_json:
        datos, archivo = request.get_json(silent=True) or {}, None
    else:
        datos, archivo = request.form, request.files.get('imagen')
    texto = validacion.validar_texto(datos.get('texto'), cfg)
    estado = validacion.leer_estado(datos.get('estado'))
    consentimiento = validacion.leer_booleano(datos.get('consentimiento'))
    # Sin consentimiento la imagen ni siquiera se decodifica: el agente solo sabe que existe (regla 3)
    imagen = archivo
    if archivo is not None and consentimiento:
        imagen = validacion.validar_imagen(archivo, cfg)

    r = _svc().agente.turno(texto, estado, imagen, consentimiento)
    ev = r.eventos
    g.evento = {
        'intencion': r.intencion, 'accion': r.accion, 'crisis': ev['crisis'], 'imagen_usada': ev['imagen_usada'],
        'aclaracion': ev['aclaracion'], 'oferta': ev['oferta'], 'tiempos': ev['tiempos'], 'error': ev['error'],
        'version_modelos': r.version_modelos,
    }
    return jsonify({'id_solicitud': g.id_solicitud, **r.publico()})


@bp.get('/metricas')
def metricas():
    if not _clave_valida(request.headers.get('X-Admin-Key', ''), _cfg().clave_admin):
        raise ErrorApi(401, 'NO_AUTORIZADO', 'Servicio no disponible.')
    return jsonify(current_app.config['METRICAS'].resumen())
