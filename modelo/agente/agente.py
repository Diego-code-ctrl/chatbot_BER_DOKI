"""
Agente híbrido por capas de DOKi. Es el único componente que invoca a los modelos.
Un turno: percibir → capa reactiva (si decide, termina) → visión → capa deliberativa → componer.
No conserva nada al terminar el turno: el estado entra y sale como diccionario.
"""
import hashlib
import json
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as TiempoAgotado
from dataclasses import dataclass, field, replace
from pathlib import Path

from modelo.agente import deliberativa, reactiva
from modelo.agente.estado import EstadoSesion
from modelo.config import MODELOS, RESULTADOS
from modelo.conocimiento import Conocimiento, cargar_conocimiento
from modelo.nlp.clasificador import ClasificadorTexto
from modelo.nlp.intenciones import es_crisis_por_reglas
from modelo.vision.inferencia import ClasificadorImagen

# Hilos para poder abandonar una inferencia visual que tarda demasiado
_EJECUTOR_VISION = ThreadPoolExecutor(max_workers=2, thread_name_prefix='vision')


@dataclass
class Resultado:
    respuesta: list[dict]
    accion: str
    intencion: str | None
    confianza_texto: float | None
    estado: dict
    version_modelos: dict
    expresion: str | None = None
    confianza_visual: float | None = None
    # Metadatos para registros y métricas; no se devuelven al cliente
    eventos: dict = field(default_factory=dict)

    def publico(self) -> dict:
        return {
            'respuesta': self.respuesta,
            'intencion': self.intencion,
            'confianza_texto': self.confianza_texto,
            'expresion': self.expresion,
            'confianza_visual': self.confianza_visual,
            'accion': self.accion,
            'estado': self.estado,
            'version_modelos': self.version_modelos,
        }


def _redondear(valor: float | None) -> float | None:
    return None if valor is None else round(float(valor), 4)


class Agente:
    def __init__(
        self,
        conocimiento: Conocimiento,
        texto: ClasificadorTexto | None,
        imagen: ClasificadorImagen | None = None,
        umbral_visual: float = 0.55,
        versiones: dict | None = None,
    ):
        self.c = conocimiento
        self.texto = texto
        self.imagen = imagen
        self.umbral_visual = umbral_visual
        self.versiones = {'conocimiento': conocimiento.version, **(versiones or {})}

    # ------------------------------------------------------------------ percepción
    def percibir(self, texto: str, hay_imagen: bool = False, consentimiento: bool = False) -> tuple[reactiva.Percepcion, dict]:
        tiempos, error = {}, None
        t = time.perf_counter()
        crisis_reglas = es_crisis_por_reglas(texto)  # no depende de ningún modelo entrenado
        pausa = reactiva.es_pausa(texto, self.c['palabras_pausa'], self.c['max_palabras_pausa'])
        tiempos['reglas_ms'] = round((time.perf_counter() - t) * 1000, 2)

        intencion = confianza = None
        terminos = 0
        if self.texto is not None:
            t = time.perf_counter()
            try:
                intencion, confianza, terminos = self.texto.clasificar(texto)
            except Exception as e:  # noqa: BLE001  (degradación segura: siguen las reglas)
                error = f'texto:{type(e).__name__}'
            tiempos['texto_ms'] = round((time.perf_counter() - t) * 1000, 2)
        else:
            error = 'texto:no_cargado'

        corta = deliberativa.respuesta_corta(texto, self.c) is not None
        p = reactiva.Percepcion(intencion, confianza, terminos, crisis_reglas, pausa, corta, hay_imagen, consentimiento)
        return p, {'tiempos': tiempos, 'error': error}

    def es_crisis(self, p: reactiva.Percepcion) -> bool:
        return reactiva.regla_crisis(p, self.c['umbral_crisis'], self.c['min_terminos_crisis'])

    # ------------------------------------------------------------------ visión
    def clasificar_imagen(self, imagen) -> tuple[str, float]:
        """Con tiempo máximo: si el modelo tarda demasiado, se abandona y el turno sigue solo con texto"""
        if self.imagen is None:
            raise RuntimeError('modelo visual no cargado')
        futuro = _EJECUTOR_VISION.submit(self.imagen, imagen)
        return futuro.result(timeout=self.c['timeout_vision_segundos'])

    def _segmento_visual(self, imagen, intencion: str, eventos: dict) -> tuple[dict, str | None, float | None]:
        t = time.perf_counter()
        try:
            expresion, confianza = self.clasificar_imagen(imagen)
        except TiempoAgotado:
            eventos['error'] = 'imagen:tiempo_agotado'
            return {'tipo': 'imagen', 'contenido': self.c.texto('imagen_fallo')}, None, None
        except Exception as e:  # noqa: BLE001
            eventos['error'] = f'imagen:{type(e).__name__}'
            return {'tipo': 'imagen', 'contenido': self.c.texto('imagen_fallo')}, None, None
        finally:
            eventos['tiempos']['imagen_ms'] = round((time.perf_counter() - t) * 1000, 2)

        if confianza < self.umbral_visual:
            contenido = self.c.vision['aviso_baja_confianza']
        elif intencion in self.c['intenciones_emocionales'] and expresion in self.c['expresiones_contrarias']:
            # El texto prevalece: no se contradice al estudiante, se explica la diferencia
            contenido = self.c.texto('contraste_imagen', expresion=expresion)
        else:
            contenido = self.c.frase_visual(expresion) or self.c.vision['aviso_baja_confianza']
        return {'tipo': 'imagen', 'contenido': contenido}, expresion, confianza

    # ------------------------------------------------------------------ turno
    def turno(self, texto: str, estado: dict | None = None, imagen=None, consentimiento: bool = False) -> Resultado:
        inicio = time.perf_counter()
        e = EstadoSesion.desde_dict(estado, self.c.intenciones, self.c['memoria_intenciones'])
        p, eventos = self.percibir(texto, imagen is not None, consentimiento)
        eventos.update(crisis=False, imagen_usada=False, aclaracion=False, oferta=None)

        def cerrar(segmentos, accion, intencion, confianza, expresion=None, confianza_visual=None) -> Resultado:
            eventos['tiempos']['total_ms'] = round((time.perf_counter() - inicio) * 1000, 2)
            return Resultado(
                respuesta=segmentos, accion=accion, intencion=intencion,
                confianza_texto=_redondear(confianza), estado=e.a_dict(), version_modelos=self.versiones,
                expresion=expresion, confianza_visual=_redondear(confianza_visual), eventos=eventos,
            )

        # ---- Capa reactiva
        # Regla 1: crisis. Se ignora la imagen y la capa deliberativa no interviene
        if self.es_crisis(p):
            e.crisis_mostrada, e.esperando_imagen, e.aclaraciones = True, False, 0
            e.recordar('crisis', self.c['memoria_intenciones'])
            eventos['crisis'] = True
            confianza = 1.0 if p.crisis_reglas else p.confianza
            return cerrar([{'tipo': 'crisis', 'contenido': self.c.respuesta('crisis')}], 'crisis', 'crisis', confianza)

        recursos = deliberativa.acompanamiento(e, self.c)
        previos = [recursos] if recursos else []

        # Respuesta a una oferta del turno anterior («sí, porfa», «no gracias»). Va antes de la
        # pausa porque «no» a secas también es una duda corta. La oferta solo dura un turno.
        pendiente, e.oferta_pendiente = e.oferta_pendiente, None
        corta = deliberativa.respuesta_corta(texto, self.c)
        aceptada = None
        if corta == 'no' and pendiente:
            return cerrar(previos + [{'tipo': 'texto', 'contenido': self.c.texto('oferta_rechazada')}], 'rechazo_oferta', pendiente, None)
        if corta == 'si':
            if not pendiente:
                return cerrar(previos + [{'tipo': 'texto', 'contenido': self.c.texto('afirmacion_sin_contexto')}], 'aclaracion', None, None)
            aceptada = pendiente

        # Regla 2: pausa
        if aceptada is None and reactiva.regla_pausa(p):
            return cerrar(previos + [{'tipo': 'texto', 'contenido': self.c.texto('pausa')}], 'pausa', 'pausa', None)

        # Sin modelo de texto: solo quedan las reglas (ya evaluadas) y una respuesta con recursos
        if p.intencion is None and aceptada is None:
            return cerrar(previos + [{'tipo': 'texto', 'contenido': self.c.texto('error_modelo_texto')}], 'error_modelo', None, None)

        # El clasificador dijo «crisis» pero la regla 1 no lo aceptó (p. ej. «nadie me entiende», con un
        # solo término conocido): se usa la siguiente intención más probable en vez de pedir aclaración
        senal_crisis = p.intencion == 'crisis' and aceptada is None and p.terminos_conocidos > 0
        if senal_crisis:
            alternativa, confianza_alt = self.texto.alternativa(texto)
            p = replace(p, intencion=alternativa, confianza=confianza_alt)

        # Regla 3: consentimiento. Sin él, el clasificador visual no se ejecuta
        usar_imagen = reactiva.regla_consentimiento(p)
        intencion = p.intencion
        if aceptada:
            intencion = aceptada  # el estudiante aceptó lo que DOKi le ofreció
        elif e.esperando_imagen and usar_imagen:
            intencion = 'compartir_imagen'  # la imagen es la respuesta a lo que DOKi pidió
        # Regla 4: baja confianza. Se pide aclaración y la imagen no se comenta
        elif reactiva.regla_baja_confianza(p, self.texto.umbral, self.c['umbral_sin_vocabulario']):
            e.aclaraciones += 1
            eventos['aclaracion'] = True
            # Si el clasificador vio una señal de crisis débil, la aclaración invita a contar más y recuerda la ayuda
            texto_aclaracion = self.c.texto('aclaracion_emocional') if senal_crisis else deliberativa.texto_aclaracion(e, self.c)
            return cerrar(previos + [{'tipo': 'texto', 'contenido': texto_aclaracion}], 'aclaracion', 'fallback', p.confianza)

        # ---- Respuesta de la intención + visión + capa deliberativa
        e.aclaraciones = 0
        variante = e.siguiente_variante(intencion)  # rota las respuestas si el tema se repite
        e.recordar(intencion, self.c['memoria_intenciones'])
        deliberativa.registrar_ofertas_implicitas(intencion, e, self.c)
        segmentos, accion = list(previos), 'responder'
        expresion = confianza_visual = None

        if intencion == 'compartir_imagen':
            if usar_imagen:
                seg, expresion, confianza_visual = self._segmento_visual(imagen, intencion, eventos)
                segmentos.append(seg)
                e.esperando_imagen = False
                eventos['imagen_usada'] = expresion is not None
            else:
                # Se pide la imagen y el consentimiento, y se espera
                segmentos.append({'tipo': 'texto', 'contenido': self.c.respuesta(intencion, variante)})
                if p.hay_imagen:
                    segmentos.append({'tipo': 'imagen', 'contenido': self.c.texto('imagen_sin_consentimiento')})
                e.esperando_imagen, accion = True, 'pedir_imagen'
        else:
            e.esperando_imagen = False
            segmentos.append({'tipo': 'texto', 'contenido': self.c.respuesta(intencion, variante)})
            e.oferta_pendiente = self.c.seguimiento(intencion)
            if intencion == 'despedida':
                accion = 'despedida'
            # Solo las intenciones de bienestar admiten un comentario sobre la imagen
            if usar_imagen and intencion in self.c.vision['intenciones_con_frase']:
                seg, expresion, confianza_visual = self._segmento_visual(imagen, intencion, eventos)
                segmentos.append(seg)
                eventos['imagen_usada'] = expresion is not None
            elif p.hay_imagen and not p.consentimiento:
                segmentos.append({'tipo': 'imagen', 'contenido': self.c.texto('imagen_sin_consentimiento')})

            oferta = deliberativa.elegir_oferta(intencion, e, self.c)
            if oferta:
                e.ofrecer(oferta)
                eventos['oferta'] = oferta
                segmentos.append({'tipo': 'oferta', 'contenido': self.c.texto(f'oferta_{oferta}')})
                e.oferta_pendiente = deliberativa.OFERTA_A_INTENCION[oferta]  # la última pregunta es la que vale

        confianza = None if aceptada else p.confianza
        return cerrar(segmentos, accion, intencion, confianza, expresion, confianza_visual)


# ---------------------------------------------------------------------- fábrica
def _huella(ruta: Path) -> str:
    return hashlib.sha256(ruta.read_bytes()).hexdigest()[:8]


def crear_agente(arquitectura: str = 'efficientnet_b0') -> tuple[Agente, dict]:
    """
    Carga cada modelo por separado: que falle uno no tumba al otro (degradación segura).
    Devuelve el agente y los errores de carga, por modelo.
    """
    conocimiento = cargar_conocimiento()
    errores, versiones = {}, {}

    texto = None
    try:
        ruta = MODELOS / 'intenciones.joblib'
        texto = ClasificadorTexto.cargar(ruta)
        versiones['texto'] = f'svm-tfidf@{_huella(ruta)}'
    except Exception as e:  # noqa: BLE001
        errores['texto'] = type(e).__name__

    imagen, umbral_visual = None, 0.55
    try:
        from modelo.vision.inferencia import crear_clasificador_visual
        ruta = MODELOS / f'vision_{arquitectura}.pt'
        imagen = crear_clasificador_visual(arquitectura, ruta)
        umbral_visual = json.loads((RESULTADOS / 'vision_umbral.json').read_text())['umbral']
        versiones['imagen'] = f'{arquitectura}@{_huella(ruta)}'
    except Exception as e:  # noqa: BLE001
        imagen = None
        errores['imagen'] = type(e).__name__

    return Agente(conocimiento, texto, imagen, umbral_visual, versiones), errores
