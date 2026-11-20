"""Casos E2–E3 (sección 9.3), degradación segura y privacidad de los registros"""
import json

from PIL import Image

from api import create_app
from api.config import Config
from api.servicios import Servicios
from modelo.agente import Agente
from tests.conftest import ImagenFalsa, requiere_texto

FOTO = Image.new('RGB', (64, 64))
H = {'X-API-Key': 'k'}


@requiere_texto
def test_e2_sin_modelo_visual_responde_con_texto(crear_agente, conocimiento):
    r = crear_agente(imagen=None).turno('estoy muy estresado con las entregas', imagen=FOTO, consentimiento=True)
    assert r.accion == 'responder' and r.respuesta[1]['contenido'] == conocimiento.texto('imagen_fallo')


@requiere_texto
def test_e2_modelo_visual_que_falla_o_tarda(crear_agente, conocimiento, monkeypatch):
    r = crear_agente(ImagenFalsa(falla=True)).turno('estoy muy estresado con las entregas', imagen=FOTO, consentimiento=True)
    assert r.respuesta[1]['contenido'] == conocimiento.texto('imagen_fallo')
    monkeypatch.setitem(conocimiento.agente, 'timeout_vision_segundos', 0.05)
    r = crear_agente(ImagenFalsa(demora=0.5)).turno('estoy muy estresado con las entregas', imagen=FOTO, consentimiento=True)
    assert r.eventos['error'] == 'imagen:tiempo_agotado' and r.accion == 'responder'


def test_e3_sin_modelo_de_texto(conocimiento):
    agente = Agente(conocimiento, texto=None)
    # Las reglas de crisis no dependen del modelo
    assert agente.turno('ya no quiero vivir').accion == 'crisis'
    r = agente.turno('estoy muy estresado')
    assert r.accion == 'error_modelo' and '800 911 2000' in r.respuesta[-1]['contenido']


def test_e3_salud_503_pero_chat_sigue(conocimiento, tmp_path):
    app = create_app(Config(clave_api='k', dir_registros=tmp_path), Servicios(Agente(conocimiento, texto=None)))
    c = app.test_client()
    assert c.get('/api/v1/salud').status_code == 503
    assert c.post('/api/v1/intencion', json={'texto': 'hola'}, headers=H).status_code == 503
    r = c.post('/api/v1/chat', json={'texto': 'quiero morir'}, headers=H)
    assert r.status_code == 200 and r.json['accion'] == 'crisis'


@requiere_texto
def test_registros_sin_contenido(texto_real, conocimiento, tmp_path):
    """Pendiente 9: ningún registro contiene texto de mensajes, respuestas ni estado"""
    app = create_app(Config(clave_api='k', dir_registros=tmp_path), Servicios(Agente(conocimiento, texto_real)))
    c = app.test_client()
    secretos = ['zanahoria morada', 'estoy muy estresado con las entregas de zanahoria', 'quiero morir zanahoria']
    for s in secretos:
        c.post('/api/v1/chat', json={'texto': s}, headers=H)
    c.post('/api/v1/chat', json={'texto': 'zanahoria ' * 60}, headers=H)  # error 400
    log = (tmp_path / 'eventos.jsonl').read_text(encoding='utf-8')
    assert 'zanahoria' not in log and 'Lamento' not in log and 'estres' not in log.replace('estres_academico', '')
    eventos = [json.loads(linea) for linea in log.splitlines()]
    assert len(eventos) == 4 and all('id' in e and 'ms' in e for e in eventos)
    assert {e['codigo'] for e in eventos} == {200, 400}
