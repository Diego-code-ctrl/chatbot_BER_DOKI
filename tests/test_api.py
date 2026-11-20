"""Casos A1–A9 (sección 9.1) sobre la API con los modelos reales"""
import io

import pytest

from api import create_app
from api.config import Config
from api.servicios import Servicios
from modelo.agente import Agente
from tests.conftest import HAY_MODELO_VISUAL, ImagenFalsa, requiere_texto

pytestmark = requiere_texto
H = {'X-API-Key': 'clave-prueba', 'X-Doki-Sesion': 'a' * 32}


@pytest.fixture(scope='module')
def servicios_reales():
    from api.servicios import cargar_servicios
    return cargar_servicios()


@pytest.fixture
def cliente(servicios_reales, tmp_path):
    cfg = Config(clave_api='clave-prueba', clave_admin='admin', dir_registros=tmp_path, limite_sesion='1000 per minute')
    return create_app(cfg, servicios_reales).test_client()


def error(r):
    return r.json['error']['codigo']


def test_a1_salud(cliente):
    r = cliente.get('/api/v1/salud')
    assert r.status_code == 200 and r.json['estado'] == 'listo'
    assert r.json['modelos']['texto'] and 'conocimiento' in r.json['version_modelos']


def test_a2_texto_valido(cliente):
    r = cliente.post('/api/v1/intencion', json={'texto': 'estoy muy estresado con las entregas'}, headers=H)
    assert r.status_code == 200 and r.json['intencion'] == 'estres_academico' and 0 <= r.json['confianza'] <= 1


def test_a3_texto_vacio(cliente):
    r = cliente.post('/api/v1/intencion', json={'texto': '   '}, headers=H)
    assert r.status_code == 400 and error(r) == 'TEXTO_INVALIDO' and r.json['error']['id_solicitud']


def test_a4_texto_largo(cliente):
    r = cliente.post('/api/v1/chat', json={'texto': 'a' * 501}, headers=H)
    assert r.status_code == 400 and error(r) == 'TEXTO_MUY_LARGO'


@pytest.mark.skipif(not HAY_MODELO_VISUAL, reason='falta el modelo visual')
def test_a5_imagen_valida(cliente, imagen_png):
    r = cliente.post('/api/v1/imagen', data={'imagen': (imagen_png(), 'cara.png')}, headers=H)
    assert r.status_code == 200 and {'expresion', 'confianza', 'supera_umbral'} <= set(r.json)


def test_a6_imagen_grande(cliente):
    grande = io.BytesIO(b'\x89PNG' + b'0' * (5 * 1024 * 1024 + 10))
    r = cliente.post('/api/v1/imagen', data={'imagen': (grande, 'g.png')}, headers=H)
    assert r.status_code == 413 and error(r) == 'IMAGEN_MUY_GRANDE'


def test_a7_formato_no_admitido(cliente, imagen_png):
    r = cliente.post('/api/v1/imagen', data={'imagen': (io.BytesIO(b'no soy imagen'), 'x.png')}, headers=H)
    assert r.status_code == 415
    r = cliente.post('/api/v1/imagen', data={'imagen': (imagen_png('GIF'), 'x.gif')}, headers=H)
    assert r.status_code == 415


def test_a8_sin_clave(cliente):
    r = cliente.post('/api/v1/chat', json={'texto': 'hola'})
    assert r.status_code == 401 and error(r) == 'NO_AUTORIZADO'
    assert cliente.post('/api/v1/chat', json={'texto': 'hola'}, headers={'X-API-Key': 'otra'}).status_code == 401


def test_a9_limite_por_sesion(servicios_reales, tmp_path):
    c = create_app(Config(clave_api='clave-prueba', dir_registros=tmp_path, limite_sesion='3 per minute'), servicios_reales).test_client()
    codigos = [c.post('/api/v1/chat', json={'texto': 'hola'}, headers=H).status_code for _ in range(4)]
    assert codigos == [200, 200, 200, 429]
    # Otra sesión no comparte el límite, aunque llegue desde la misma IP (el servidor de Streamlit)
    assert c.post('/api/v1/chat', json={'texto': 'hola'}, headers={**H, 'X-Doki-Sesion': 'b' * 32}).status_code == 200


def test_a9_limite_global(servicios_reales, tmp_path):
    c = create_app(Config(clave_api='clave-prueba', dir_registros=tmp_path, limite_global='2 per minute'), servicios_reales).test_client()
    codigos = [c.post('/api/v1/chat', json={'texto': 'hola'}, headers={**H, 'X-Doki-Sesion': f'{i:032x}'}).status_code for i in range(3)]
    assert codigos == [200, 200, 429]


def test_chat_contrato_completo(cliente):
    r = cliente.post('/api/v1/chat', json={'texto': 'estoy muy estresado con las entregas', 'estado': {}}, headers=H)
    campos = {'id_solicitud', 'respuesta', 'intencion', 'confianza_texto', 'expresion', 'confianza_visual', 'accion', 'estado', 'version_modelos'}
    assert r.status_code == 200 and campos == set(r.json)
    assert all({'tipo', 'contenido'} == set(s) for s in r.json['respuesta'])


def test_chat_multipart_con_imagen(servicios_reales, tmp_path, imagen_png):
    agente = Agente(servicios_reales.agente.c, servicios_reales.agente.texto, ImagenFalsa('tristeza', 0.9))
    c = create_app(Config(clave_api='clave-prueba', dir_registros=tmp_path), Servicios(agente)).test_client()
    r = c.post('/api/v1/chat', headers=H, data={
        'texto': 'estoy muy estresado con las entregas', 'estado': '{}', 'consentimiento': 'true', 'imagen': (imagen_png(), 'c.png'),
    })
    assert r.status_code == 200 and r.json['expresion'] == 'tristeza'


def test_estado_invalido(cliente):
    r = cliente.post('/api/v1/chat', data={'texto': 'hola', 'estado': '{no es json'}, headers=H)
    assert r.status_code == 400 and error(r) == 'ESTADO_INVALIDO'


def test_errores_siempre_con_formato_uniforme(cliente):
    for r in [cliente.get('/api/v1/no-existe'), cliente.get('/api/v1/chat', headers=H), cliente.get('/api/v1/metricas')]:
        assert set(r.json['error']) == {'codigo', 'mensaje', 'id_solicitud'}


def test_metricas(cliente):
    cliente.post('/api/v1/chat', json={'texto': 'ya no quiero vivir'}, headers=H)
    m = cliente.get('/api/v1/metricas', headers={'X-Admin-Key': 'admin'}).json
    assert m['activaciones']['crisis'] >= 1 and m['latencia_ms']['/api/v1/chat']['p95'] is not None
