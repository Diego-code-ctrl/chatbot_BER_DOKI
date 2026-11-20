"""
Ejecuta los casos de la sección 9 que pueden automatizarse (A1–A9, G1–G10, E1–E4) con los modelos
reales y anota lo observado: códigos, acciones, intenciones y confianzas. Escribe resultados/casos_prueba.csv.
U1–U6 y E5 son manuales y se registran sobre la aplicación desplegada.

    python -m scripts.ejecutar_casos

En G3, G4 y G7 la expresión de la imagen se fija con un clasificador simulado: el repositorio no
incluye fotos de rostros y lo que se prueba es la política del agente, no el modelo visual.
"""
import csv
import io
import os
import sys
import tempfile
import threading
from pathlib import Path

from PIL import Image

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from api import create_app  # noqa: E402
from api.config import Config  # noqa: E402
from api.servicios import Servicios, cargar_servicios  # noqa: E402
from modelo.agente import Agente  # noqa: E402
from modelo.conocimiento import cargar_conocimiento  # noqa: E402
from modelo.nlp.clasificador import ClasificadorTexto  # noqa: E402

CLAVE = 'clave-de-prueba'
H = {'X-API-Key': CLAVE}
filas: list[tuple[str, str, bool]] = []


def anotar(caso: str, obtenido: str, cumple: bool) -> None:
    filas.append((caso, obtenido, cumple))
    print(f"{caso:4} {'Sí' if cumple else 'NO'}  {obtenido}")


def imagen(formato='PNG', tamano=(224, 224)) -> io.BytesIO:
    muestra = RAIZ / 'resultados' / 'fer2013_muestras.png'
    img = Image.open(muestra).convert('RGB').crop((0, 0, 150, 150)) if muestra.exists() else Image.new('RGB', tamano, 'gray')
    b = io.BytesIO()
    img.save(b, formato)
    b.seek(0)
    return b


class ExpresionFija:
    def __init__(self, expresion, confianza=0.9):
        self.expresion, self.confianza, self.llamadas = expresion, confianza, 0

    def __call__(self, img):
        self.llamadas += 1
        return self.expresion, self.confianza


def casos_api() -> None:
    svc = cargar_servicios()
    cfg = Config(clave_api=CLAVE, dir_registros=Path(tempfile.mkdtemp()))
    c = create_app(cfg, svc).test_client()

    r = c.get('/api/v1/salud')
    anotar('A1', f"{r.status_code}; estado={r.json['estado']}; versiones={r.json.get('versiones') or r.json.get('version_modelos')}",
           r.status_code == 200 and r.json['estado'] == 'listo')
    r = c.post('/api/v1/intencion', json={'texto': 'estoy muy estresado por las entregas de la escuela'}, headers=H)
    anotar('A2', f"{r.status_code}; intención={r.json['intencion']}; confianza={r.json['confianza']:.2f}", r.status_code == 200 and 'intencion' in r.json)
    r = c.post('/api/v1/intencion', json={'texto': '   '}, headers=H)
    anotar('A3', f"{r.status_code}; código={r.json['error']['codigo']}", r.status_code == 400)
    r = c.post('/api/v1/chat', json={'texto': 'a' * 501}, headers=H)
    anotar('A4', f"{r.status_code}; código={r.json['error']['codigo']}", r.status_code == 400)
    r = c.post('/api/v1/imagen', data={'imagen': (imagen(), 'rostro.png')}, headers=H)
    anotar('A5', f"{r.status_code}; expresión={r.json.get('expresion')}; confianza={r.json.get('confianza', 0):.2f}; supera_umbral={r.json.get('supera_umbral')}",
           r.status_code == 200 and 'expresion' in r.json)
    r = c.post('/api/v1/imagen', data={'imagen': (io.BytesIO(b'\x89PNG' + b'0' * (5 * 1024 * 1024 + 10)), 'g.png')}, headers=H)
    anotar('A6', f"{r.status_code}; código={r.json['error']['codigo']}", r.status_code == 413)
    r1 = c.post('/api/v1/imagen', data={'imagen': (io.BytesIO(b'no soy imagen'), 'x.png')}, headers=H)
    r2 = c.post('/api/v1/imagen', data={'imagen': (imagen('GIF'), 'x.gif')}, headers=H)
    anotar('A7', f"texto disfrazado: {r1.status_code}; GIF: {r2.status_code}; código={r1.json['error']['codigo']}", r1.status_code == r2.status_code == 415)
    r = c.post('/api/v1/chat', json={'texto': 'hola'})
    anotar('A8', f"{r.status_code}; código={r.json['error']['codigo']}; mensaje=«{r.json['error']['mensaje']}»", r.status_code == 401)
    limitada = create_app(Config(clave_api=CLAVE, dir_registros=Path(tempfile.mkdtemp())), svc).test_client()
    sesion = {**H, 'X-Doki-Sesion': 'a' * 32}
    codigos = [limitada.post('/api/v1/chat', json={'texto': 'hola'}, headers=sesion).status_code for _ in range(22)]
    otra = limitada.post('/api/v1/chat', json={'texto': 'hola'}, headers={**H, 'X-Doki-Sesion': 'b' * 32}).status_code
    primero_429 = codigos.index(429) + 1 if 429 in codigos else None
    anotar('A9', f"22 solicitudes de una sesión: 200 hasta la {codigos.count(200)}.ª, 429 desde la {primero_429}.ª (límite 20/min); otra sesión al mismo tiempo: {otra}",
           codigos.count(200) == 20 and primero_429 == 21 and otra == 200)


def casos_agente() -> None:
    c, texto = cargar_conocimiento(), ClasificadorTexto.cargar()

    def agente(img=None):
        return Agente(c, texto, img, umbral_visual=0.55, versiones={})

    foto = Image.new('RGB', (64, 64))
    r = agente().turno('hola, buenos días')
    anotar('G1', f"acción={r.accion}; intención={r.intencion} ({r.confianza_texto:.2f})", r.intencion == 'saludo')
    r = agente().turno('ya no quiero vivir')
    anotar('G2', f"acción={r.accion}; segmentos={[s['tipo'] for s in r.respuesta]}; incluye 911 y línea de contacto: {'911' in str(r.respuesta) and '722 276 7190' in str(r.respuesta)}",
           r.accion == 'crisis' and '911' in str(r.respuesta))
    alegre = ExpresionFija('alegría', 0.95)
    r = agente(alegre).turno('quiero morir', imagen=foto, consentimiento=True)
    anotar('G3', f"acción={r.accion}; modelo visual llamado {alegre.llamadas} veces; expresión en la respuesta={r.expresion}",
           r.accion == 'crisis' and alegre.llamadas == 0)
    r = agente(ExpresionFija('tristeza', 0.9)).turno('te comparto una foto', imagen=foto, consentimiento=True)
    visual = [s['contenido'] for s in r.respuesta if s['tipo'] == 'imagen']
    anotar('G4', f"acción={r.accion}; expresión={r.expresion} ({r.confianza_visual}); frase=«{visual[0] if visual else '—'}»",
           r.accion != 'crisis' and bool(visual))
    sin_permiso = ExpresionFija('tristeza')
    r = agente(sin_permiso).turno('estoy muy estresado por los exámenes', imagen=foto, consentimiento=False)
    anotar('G5', f"acción={r.accion}; modelo visual llamado {sin_permiso.llamadas} veces; expresión={r.expresion}",
           sin_permiso.llamadas == 0 and r.expresion is None)
    r = agente().turno('qwerty asdf')
    anotar('G6', f"acción={r.accion}; confianza={r.confianza_texto}", r.accion == 'aclaracion')
    r = agente(ExpresionFija('alegría', 0.9)).turno('estoy muy estresado con las entregas', imagen=foto, consentimiento=True)
    visual = [s['contenido'] for s in r.respuesta if s['tipo'] == 'imagen']
    anotar('G7', f"intención={r.intencion}; expresión={r.expresion}; frase=«{visual[0] if visual else '—'}»",
           r.intencion == 'estres_academico' and bool(visual) and visual[0] == c.texto('contraste_imagen', expresion='alegría'))
    r = agente().turno('mmm no sé')
    anotar('G8', f"acción={r.accion}", r.accion == 'pausa')
    estado, textos, ofertas = {}, [], []
    for t in ['estoy muy estresado con las entregas', 'tengo ansiedad por el examen', 'sigo muy estresado con las tareas', 'otra vez estresado con la escuela']:
        r = agente().turno(t, estado)
        estado = r.estado
        textos.append(r.respuesta[0]['contenido'])
        ofertas += [s['contenido'] for s in r.respuesta if s['tipo'] == 'oferta']
    anotar('G9', f"4 turnos: {len(set(textos))} respuestas distintas; ofertas de cita en la conversación: {len(ofertas)}; memoria={estado['intenciones']}",
           len(set(textos)) == 4 and len(ofertas) == 1)
    obs = [(t, agente().turno(t)) for t in ['¿quién ganó el partido?', 'recomiéndame una película']]
    anotar('G10', '; '.join(f"«{t}» → {r.accion}/{r.intencion}" for t, r in obs), all(r.accion != 'crisis' for _, r in obs))


def casos_errores() -> None:
    c, texto = cargar_conocimiento(), ClasificadorTexto.cargar()
    from streamlit.testing.v1 import AppTest
    os.chdir(RAIZ.anchor)  # que no se lea .streamlit/secrets.toml local

    def interfaz(url, clave, mensaje):
        os.environ['DOKI_API_URL'], os.environ['DOKI_API_KEY'] = url, clave
        at = AppTest.from_file(str(RAIZ / 'app' / 'main.py'), default_timeout=30)
        at.run()
        at.button[0].click().run()
        at.chat_input[0].set_value(mensaje).run()
        return at, ' '.join(m.value for x in at.chat_message for m in x.markdown)

    at, t = interfaz('http://127.0.0.1:9', 'k', 'hola')
    anotar('E1', f"aviso «no está disponible»: {'no está disponible' in t}; botón Reintentar: {any(b.label == 'Reintentar' for b in at.button)}; "
                 f"banner presente: {any('doki-ayuda' in m.value for m in at.markdown)}",
           'no está disponible' in t and any(b.label == 'Reintentar' for b in at.button))
    r = Agente(c, texto, None, 0.55, {}).turno('estoy muy estresado con las entregas', imagen=Image.new('RGB', (64, 64)), consentimiento=True)
    anotar('E2', f"acción={r.accion}; segmentos={[s['tipo'] for s in r.respuesta]}; aviso=«{r.respuesta[-1]['contenido']}»",
           r.accion == 'responder' and r.respuesta[-1]['contenido'] == c.texto('imagen_fallo'))
    sin_texto = Agente(c, None)
    r1, r2 = sin_texto.turno('ya no quiero vivir'), sin_texto.turno('estoy muy estresado')
    app = create_app(Config(clave_api=CLAVE, dir_registros=Path(tempfile.mkdtemp())), Servicios(sin_texto)).test_client()
    anotar('E3', f"crisis por reglas: {r1.accion}; mensaje común: {r2.accion} con Línea de la Vida: {'800 911 2000' in str(r2.respuesta)}; "
                 f"/salud: {app.get('/api/v1/salud').status_code}", r1.accion == 'crisis' and r2.accion == 'error_modelo')

    from werkzeug.serving import make_server
    srv = make_server('127.0.0.1', 0, create_app(Config(clave_api='correcta', dir_registros=Path(tempfile.mkdtemp())), Servicios(Agente(c, texto))))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        _, t = interfaz(f'http://127.0.0.1:{srv.server_port}', 'incorrecta', 'hola')
    finally:
        srv.shutdown()
    anotar('E4', f"aviso «no está disponible»: {'no está disponible' in t}; muestra 401 o código técnico: {'401' in t or 'NO_AUTORIZADO' in t}",
           'no está disponible' in t and '401' not in t and 'NO_AUTORIZADO' not in t)


def main() -> None:
    casos_api()
    casos_agente()
    casos_errores()
    with open(RAIZ / 'resultados' / 'casos_prueba.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['caso', 'resultado_obtenido', 'cumple'])
        w.writerows((caso, obt, 'Sí' if ok else 'No') for caso, obt, ok in filas)
    print(f"\n{sum(ok for *_, ok in filas)}/{len(filas)} casos cumplen")


if __name__ == '__main__':
    main()
