"""Casos E1 y E4 (sección 9.3) e interfaz sin API. La interfaz se prueba con streamlit.testing"""
import sys
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parent.parent / 'app'
sys.path.insert(0, str(APP))

from crisis_local import parece_crisis  # noqa: E402

AppTest = pytest.importorskip('streamlit.testing.v1').AppTest


@pytest.mark.parametrize('texto', ['ya no quiero vivir', 'Pienso en SUICIDARME', 'me hago cortes', 'quiero desaparecer'])
def test_crisis_local_detecta(texto):
    assert parece_crisis(texto)


@pytest.mark.parametrize('texto', ['hola', 'estoy estresado por el examen', 'no puedo dormir'])
def test_crisis_local_no_alarma(texto):
    assert not parece_crisis(texto)


def _abrir(monkeypatch, url, clave='k'):
    # Fuera del repositorio, para que no se lea .streamlit/secrets.toml local (tendría prioridad)
    monkeypatch.chdir(APP.anchor)
    monkeypatch.setenv('DOKI_API_URL', url)
    monkeypatch.setenv('DOKI_API_KEY', clave)
    at = AppTest.from_file(str(APP / 'main.py'), default_timeout=30)
    at.run()
    at.button[0].click().run()  # acepta el aviso inicial
    return at


def _textos(at):
    return ' '.join(m.value for c in at.chat_message for m in c.markdown)


def test_e1_api_apagada(monkeypatch):
    at = _abrir(monkeypatch, 'http://127.0.0.1:9')  # puerto cerrado
    assert 'no está disponible' in ' '.join(m.value for m in at.markdown)
    at.chat_input[0].set_value('quiero morir').run()
    texto = _textos(at)
    assert 'Línea de la Vida' in texto and 'no está disponible' in texto  # protocolo local + aviso
    assert any(b.label == 'Reintentar' for b in at.button)


def test_e4_clave_incorrecta_sin_detalles(monkeypatch, tmp_path):
    import threading
    from werkzeug.serving import make_server
    from api import create_app
    from api.config import Config
    from api.servicios import Servicios
    from modelo.agente import Agente
    from modelo.conocimiento import cargar_conocimiento

    app = create_app(Config(clave_api='correcta', dir_registros=tmp_path), Servicios(Agente(cargar_conocimiento(), None)))
    servidor = make_server('127.0.0.1', 0, app)
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    try:
        at = _abrir(monkeypatch, f'http://127.0.0.1:{servidor.server_port}', clave='incorrecta')
        at.chat_input[0].set_value('hola').run()
        texto = _textos(at)
        assert 'no está disponible' in texto and '401' not in texto and 'NO_AUTORIZADO' not in texto
    finally:
        servidor.shutdown()
