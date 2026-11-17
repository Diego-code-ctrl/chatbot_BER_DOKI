"""Formato de error único: {'error': {'codigo', 'mensaje', 'id_solicitud'}}"""
from flask import g, jsonify
from werkzeug.exceptions import HTTPException

CODIGOS_HTTP = {
    404: 'RUTA_NO_ENCONTRADA', 405: 'METODO_NO_PERMITIDO', 413: 'IMAGEN_MUY_GRANDE',
    415: 'FORMATO_NO_ADMITIDO', 429: 'DEMASIADAS_SOLICITUDES',
}
MENSAJES_HTTP = {429: 'Demasiadas solicitudes. Espera unos segundos.', 413: 'La imagen supera el tamaño máximo permitido.'}


class ErrorApi(Exception):
    def __init__(self, http: int, codigo: str, mensaje: str):
        super().__init__(mensaje)
        self.http = http
        self.codigo = codigo
        self.mensaje = mensaje


def respuesta_error(http: int, codigo: str, mensaje: str):
    g.codigo_error = codigo
    cuerpo = {'error': {'codigo': codigo, 'mensaje': mensaje, 'id_solicitud': getattr(g, 'id_solicitud', None)}}
    return jsonify(cuerpo), http


def registrar_manejadores(app) -> None:
    @app.errorhandler(ErrorApi)
    def _error_api(e: ErrorApi):
        return respuesta_error(e.http, e.codigo, e.mensaje)

    @app.errorhandler(HTTPException)
    def _error_http(e: HTTPException):
        codigo = e.code or 500
        return respuesta_error(codigo, CODIGOS_HTTP.get(codigo, 'ERROR_HTTP'), MENSAJES_HTTP.get(codigo, 'Solicitud no válida.'))

    @app.errorhandler(Exception)
    def _error_interno(e: Exception):
        # Solo el tipo de error, nunca el contenido de la solicitud
        g.error_interno = f'interno:{type(e).__name__}'
        return respuesta_error(500, 'ERROR_INTERNO', 'Ocurrió un error interno.')
