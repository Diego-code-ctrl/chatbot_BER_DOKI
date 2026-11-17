"""Contadores agregados en memoria, sin contenido de mensajes. Se reinician con la API"""
import threading
import time
from collections import Counter, defaultdict, deque

VENTANA_LATENCIAS = 1000


def _percentil(valores: list[float], q: float) -> float | None:
    if not valores:
        return None
    ordenados = sorted(valores)
    indice = min(len(ordenados) - 1, max(0, round(q * (len(ordenados) - 1))))
    return round(ordenados[indice], 1)


class Metricas:
    def __init__(self):
        self._lock = threading.Lock()  # Waitress atiende con varios hilos
        self.inicio = time.time()
        self.solicitudes = Counter()
        self.errores = Counter()
        self.acciones = Counter()
        self.intenciones = Counter()
        self.banderas = Counter()
        self.latencias = defaultdict(lambda: deque(maxlen=VENTANA_LATENCIAS))

    def registrar(self, ruta: str, codigo: int, ms: float, evento: dict) -> None:
        with self._lock:
            self.solicitudes[ruta] += 1
            self.latencias[ruta].append(ms)
            if codigo >= 400:
                self.errores[evento.get('codigo_error') or str(codigo)] += 1
            if evento.get('accion'):
                self.acciones[evento['accion']] += 1
            if evento.get('intencion'):
                self.intenciones[evento['intencion']] += 1
            for bandera in ('crisis', 'imagen_usada', 'aclaracion'):
                if evento.get(bandera):
                    self.banderas[bandera] += 1
            if evento.get('error'):
                self.errores[evento['error']] += 1

    def resumen(self) -> dict:
        with self._lock:
            turnos = self.solicitudes.get('/api/v1/chat', 0)
            return {
                'desde_arranque_s': round(time.time() - self.inicio),
                'solicitudes': dict(self.solicitudes),
                'errores': dict(self.errores),
                'acciones': dict(self.acciones),
                'intenciones': dict(self.intenciones),
                'activaciones': dict(self.banderas),
                'tasas_chat': {
                    'crisis': round(self.banderas['crisis'] / turnos, 4) if turnos else None,
                    'aclaracion': round(self.banderas['aclaracion'] / turnos, 4) if turnos else None,
                },
                'latencia_ms': {
                    ruta: {'p50': _percentil(list(v), .5), 'p95': _percentil(list(v), .95), 'p99': _percentil(list(v), .99), 'n': len(v)}
                    for ruta, v in self.latencias.items()
                },
            }
