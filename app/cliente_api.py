"""
Cliente HTTP de la API de DOKi. Es lo único que la interfaz necesita para consumirla:
`ClienteApi.chat(...)` devuelve el contrato de /api/v1/chat y levanta `ErrorApi` ante cualquier fallo.
No reintenta solo: un reintento silencioso podría duplicar un turno de crisis.
"""
import json
from dataclasses import dataclass

import requests

from config import TIMEOUT_CONEXION, TIMEOUT_RESPUESTA


class ErrorApi(Exception):
    def __init__(self, http: int | None, codigo: str, mensaje: str, id_solicitud: str | None = None):
        super().__init__(mensaje)
        self.http, self.codigo, self.mensaje, self.id_solicitud = http, codigo, mensaje, id_solicitud


@dataclass(frozen=True)
class Imagen:
    contenido: bytes
    nombre: str
    tipo: str


class ClienteApi:
    def __init__(self, url_base: str, clave: str, sesion: str = ''):
        self.base = f'{url_base}/api/v1'
        # X-Doki-Sesion: identificador aleatorio de la pestaña; la API limita la frecuencia por él
        self.cabeceras = {'X-API-Key': clave, **({'X-Doki-Sesion': sesion} if sesion else {})}

    def _llamar(self, metodo: str, ruta: str, **kwargs) -> dict:
        try:
            r = requests.request(
                metodo, f'{self.base}{ruta}', headers=self.cabeceras,
                timeout=(TIMEOUT_CONEXION, TIMEOUT_RESPUESTA), **kwargs,
            )
        except requests.Timeout:
            raise ErrorApi(None, 'TIEMPO_AGOTADO', 'La API tardó demasiado en responder.')
        except requests.RequestException:
            raise ErrorApi(None, 'SIN_CONEXION', 'No se pudo conectar con la API.')
        try:
            cuerpo = r.json()
        except ValueError:
            cuerpo = {}
        if r.ok:
            return cuerpo
        error = cuerpo.get('error', {})
        raise ErrorApi(r.status_code, error.get('codigo', 'ERROR_HTTP'), error.get('mensaje', ''), error.get('id_solicitud'))

    def salud(self) -> dict:
        return self._llamar('GET', '/salud')

    def chat(self, texto: str, estado: dict, imagen: Imagen | None = None, consentimiento: bool = False) -> dict:
        if imagen is None:
            return self._llamar('POST', '/chat', json={'texto': texto, 'estado': estado, 'consentimiento': False})
        return self._llamar(
            'POST', '/chat',
            data={'texto': texto, 'estado': json.dumps(estado), 'consentimiento': str(consentimiento).lower()},
            files={'imagen': (imagen.nombre, imagen.contenido, imagen.tipo)},
        )
