"""
Memoria de sesión del agente. Solo etiquetas y contadores: nunca texto de mensajes ni imágenes.
Viaja con cada solicitud (la API no guarda estado), por eso se sanea al recibirla: viene del cliente.
"""
from dataclasses import asdict, dataclass, field

MAX_VISTAS = 99

OFERTAS = ('cita', 'respiracion')
MAX_ACLARACIONES = 10


@dataclass
class EstadoSesion:
    intenciones: list[str] = field(default_factory=list)  # las más recientes, la última al final
    aclaraciones: int = 0                                  # aclaraciones seguidas
    esperando_imagen: bool = False
    ofertas: list[str] = field(default_factory=list)       # ofertas ya hechas en la sesión
    crisis_mostrada: bool = False
    oferta_pendiente: str | None = None                    # intención que DOKi acaba de ofrecer
    vistas: dict[str, int] = field(default_factory=dict)   # respuestas dadas por intención (rota variantes)

    @classmethod
    def desde_dict(cls, datos, intenciones_validas, memoria: int) -> 'EstadoSesion':
        datos = datos if isinstance(datos, dict) else {}
        intenciones = datos.get('intenciones')
        intenciones = [i for i in intenciones if isinstance(i, str) and i in intenciones_validas] if isinstance(intenciones, list) else []
        aclaraciones = datos.get('aclaraciones')
        aclaraciones = aclaraciones if isinstance(aclaraciones, int) and not isinstance(aclaraciones, bool) else 0
        ofertas = datos.get('ofertas')
        ofertas = [o for o in OFERTAS if isinstance(ofertas, list) and o in ofertas]
        return cls(
            intenciones=intenciones[-memoria:],
            aclaraciones=min(max(aclaraciones, 0), MAX_ACLARACIONES),
            esperando_imagen=datos.get('esperando_imagen') is True,
            ofertas=ofertas,
            crisis_mostrada=datos.get('crisis_mostrada') is True,
            oferta_pendiente=datos.get('oferta_pendiente') if datos.get('oferta_pendiente') in intenciones_validas else None,
            vistas={
                k: min(v, MAX_VISTAS) for k, v in (datos.get('vistas') or {}).items()
                if k in intenciones_validas and isinstance(v, int) and not isinstance(v, bool) and v >= 0
            } if isinstance(datos.get('vistas'), dict) else {},
        )

    def recordar(self, intencion: str, memoria: int) -> None:
        self.intenciones = (self.intenciones + [intencion])[-memoria:]

    def siguiente_variante(self, intencion: str) -> int:
        n = self.vistas.get(intencion, 0)
        self.vistas[intencion] = min(n + 1, MAX_VISTAS)
        return n

    def ofrecer(self, oferta: str) -> None:
        if oferta not in self.ofertas:
            self.ofertas.append(oferta)

    def a_dict(self) -> dict:
        return asdict(self)
