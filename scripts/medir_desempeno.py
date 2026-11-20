"""
Mediciones locales de la sección 10.2: latencia de texto e imagen en la API (mediana y p95),
primera solicitud tras iniciar, memoria con los modelos cargados y una prueba de carga corta.
Arranca su propia API (Waitress) en un puerto libre, con una clave temporal y registros aparte.

    python -m scripts.medir_desempeno            # escribe resultados/desempeno_local.{csv,json}

No mide la red (túnel y Streamlit Cloud): esa latencia se toma con la aplicación desplegada.
"""
import io
import json
import os
import platform
import secrets
import socket
import statistics
import subprocess
import sys
import tempfile
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests
from PIL import Image

RAIZ = Path(__file__).resolve().parent.parent
RESULTADOS = RAIZ / 'resultados'
TEXTOS = [
    'estoy muy estresado por los exámenes', 'no puedo dormir bien', 'quiero agendar una cita',
    'cómo organizo mis tareas', 'hola', 'me siento triste estos días', 'dónde está el servicio de orientación',
]
N_TEXTO, N_IMAGEN = 100, 40
CARGA_HILOS, CARGA_SOLICITUDES = 8, 200


def _puerto_libre() -> int:
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def _imagen() -> bytes:
    """Una imagen JPEG de 640×480; el modelo la redimensiona, así que el contenido no cambia el costo"""
    muestra = RESULTADOS / 'fer2013_muestras.png'
    img = Image.open(muestra).convert('RGB').resize((640, 480)) if muestra.exists() else Image.new('RGB', (640, 480), 'gray')
    buf = io.BytesIO()
    img.save(buf, 'JPEG', quality=90)
    return buf.getvalue()


def _percentiles(ms: list[float]) -> dict:
    ms = sorted(ms)
    return {
        'n': len(ms), 'mediana_ms': round(statistics.median(ms), 1),
        'p95_ms': round(ms[max(0, int(round(0.95 * len(ms))) - 1)], 1), 'max_ms': round(ms[-1], 1),
    }


def _memoria_mb(pid: int) -> float:
    rss_kb = int(subprocess.run(['ps', '-o', 'rss=', '-p', str(pid)], capture_output=True, text=True).stdout.strip() or 0)
    return round(rss_kb / 1024, 1)


def _cabeceras(clave: str, sesion: str | None = None) -> dict:
    return {'X-API-Key': clave, 'X-Doki-Sesion': sesion or uuid.uuid4().hex}


def medir() -> dict:
    clave, puerto = secrets.token_hex(16), _puerto_libre()
    base = f'http://127.0.0.1:{puerto}/api/v1'
    entorno = {
        **os.environ, 'DOKI_API_KEY': clave, 'DOKI_ADMIN_KEY': secrets.token_hex(16),
        'DOKI_API_PUERTO': str(puerto), 'DOKI_DIR_REGISTROS': tempfile.mkdtemp(prefix='doki_logs_'),
        # Límites altos solo para medir: aquí interesa la capacidad del equipo, no la política
        'DOKI_LIMITE_SESION': '100000 per minute', 'DOKI_LIMITE_GLOBAL': '100000 per minute',
    }
    inicio = time.perf_counter()
    proc = subprocess.Popen([sys.executable, '-m', 'api.servidor'], cwd=RAIZ, env=entorno,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        # 1. Arranque y primera solicitud
        while True:
            try:
                if requests.get(f'{base}/salud', timeout=1).ok:
                    break
            except requests.RequestException:
                pass
            if proc.poll() is not None or time.perf_counter() - inicio > 180:
                raise RuntimeError('La API no arrancó')
            time.sleep(0.2)
        arranque_s = time.perf_counter() - inicio
        salud = requests.get(f'{base}/salud', timeout=5).json()
        t = time.perf_counter()
        requests.post(f'{base}/chat', json={'texto': 'hola', 'estado': {}}, headers=_cabeceras(clave), timeout=60).raise_for_status()
        primera_ms = (time.perf_counter() - t) * 1000
        memoria_reposo = _memoria_mb(proc.pid)

        # 2. Texto: turno completo de /chat (agente + clasificador), secuencial
        texto_ms = []
        for i in range(N_TEXTO):
            t = time.perf_counter()
            r = requests.post(f'{base}/chat', json={'texto': TEXTOS[i % len(TEXTOS)], 'estado': {}}, headers=_cabeceras(clave), timeout=30)
            texto_ms.append((time.perf_counter() - t) * 1000)
            r.raise_for_status()

        # 3. Imagen: /chat con imagen y consentimiento (texto + visión), secuencial
        imagen, imagen_ms, primera_imagen_ms = _imagen(), [], None
        for i in range(N_IMAGEN + 1):
            t = time.perf_counter()
            r = requests.post(
                f'{base}/chat', headers=_cabeceras(clave), timeout=60,
                data={'texto': 'te comparto una foto', 'estado': '{}', 'consentimiento': 'true'},
                files={'imagen': ('foto.jpg', imagen, 'image/jpeg')},
            )
            ms = (time.perf_counter() - t) * 1000
            r.raise_for_status()
            if i == 0:
                primera_imagen_ms = ms  # calienta el modelo visual; se reporta aparte
            else:
                imagen_ms.append(ms)
        memoria_modelos = _memoria_mb(proc.pid)

        # 4. Carga corta: varias sesiones simultáneas solo con texto
        def una(i: int) -> tuple[int, float]:
            t = time.perf_counter()
            r = requests.post(f'{base}/chat', json={'texto': TEXTOS[i % len(TEXTOS)], 'estado': {}}, headers=_cabeceras(clave), timeout=30)
            return r.status_code, (time.perf_counter() - t) * 1000

        t = time.perf_counter()
        with ThreadPoolExecutor(CARGA_HILOS) as ex:
            res = list(ex.map(una, range(CARGA_SOLICITUDES)))
        duracion = time.perf_counter() - t
        ok = [ms for codigo, ms in res if codigo == 200]
        memoria_carga = _memoria_mb(proc.pid)

        return {
            'equipo': {'sistema': f'{platform.system()} {platform.machine()}', 'python': platform.python_version(),
                       'procesador': platform.processor() or platform.machine(), 'nucleos': os.cpu_count()},
            'versiones': salud.get('versiones') or salud.get('version_modelos'),
            'arranque_hasta_salud_s': round(arranque_s, 2),
            'primera_solicitud_texto_ms': round(primera_ms, 1),
            'primera_solicitud_imagen_ms': round(primera_imagen_ms, 1),
            'texto': _percentiles(texto_ms),
            'imagen': _percentiles(imagen_ms),
            'memoria_mb': {'tras_arranque': memoria_reposo, 'tras_imagenes': memoria_modelos, 'tras_carga': memoria_carga},
            'carga': {
                'hilos': CARGA_HILOS, 'solicitudes': CARGA_SOLICITUDES, 'exitosas': len(ok),
                'errores': CARGA_SOLICITUDES - len(ok), 'solicitudes_por_segundo': round(CARGA_SOLICITUDES / duracion, 1),
                **(_percentiles(ok) if ok else {}),
            },
        }
    finally:
        proc.terminate()
        proc.wait(timeout=10)


def main() -> None:
    r = medir()
    RESULTADOS.mkdir(exist_ok=True)
    (RESULTADOS / 'desempeno_local.json').write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding='utf-8')
    filas = [
        ('Latencia de texto en la API', 'Solo texto, en local', f"mediana {r['texto']['mediana_ms']} ms; p95 {r['texto']['p95_ms']} ms (n={r['texto']['n']})"),
        ('Latencia de imagen en la API', 'Texto e imagen, en local', f"mediana {r['imagen']['mediana_ms']} ms; p95 {r['imagen']['p95_ms']} ms (n={r['imagen']['n']})"),
        ('Primera solicitud tras iniciar la API', 'Con la carga de modelos',
         f"arranque {r['arranque_hasta_salud_s']} s; primer texto {r['primera_solicitud_texto_ms']} ms; primera imagen {r['primera_solicitud_imagen_ms']} ms"),
        ('Memoria de la API con los modelos cargados', 'Equipo local',
         f"{r['memoria_mb']['tras_arranque']} MB al arrancar; {r['memoria_mb']['tras_imagenes']} MB tras usar el modelo visual; {r['memoria_mb']['tras_carga']} MB tras la carga"),
        ('Varias solicitudes simultáneas', 'Prueba de carga corta',
         f"{r['carga']['hilos']} sesiones, {r['carga']['solicitudes']} solicitudes: {r['carga']['exitosas']} correctas, "
         f"{r['carga']['solicitudes_por_segundo']} solicitudes/s, mediana {r['carga'].get('mediana_ms')} ms, p95 {r['carga'].get('p95_ms')} ms"),
    ]
    with open(RESULTADOS / 'desempeno_local.csv', 'w', encoding='utf-8') as f:
        f.write('medicion,condicion,resultado\n')
        for fila in filas:
            f.write(','.join(f'"{c}"' for c in fila) + '\n')
    print(json.dumps(r, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
