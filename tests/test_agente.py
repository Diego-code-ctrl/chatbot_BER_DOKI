"""Casos G1–G10 (sección 9.2) y pruebas unitarias de las capas del agente"""
import pytest
from PIL import Image

from modelo.agente import reactiva
from modelo.agente.estado import EstadoSesion
from tests.conftest import ImagenFalsa

FOTO = Image.new('RGB', (64, 64))


def tipos(r):
    return [s['tipo'] for s in r.respuesta]


# ---------------------------------------------------------------- G1–G10
def test_g1_saludo(crear_agente):
    r = crear_agente().turno('hola, buenas tardes')
    assert (r.intencion, r.accion) == ('saludo', 'responder')


def test_g2_crisis_explicita(crear_agente):
    r = crear_agente().turno('ya no quiero vivir')
    assert r.accion == 'crisis' and tipos(r) == ['crisis']
    assert r.estado['crisis_mostrada'] is True


def test_g2_crisis_detectada_solo_por_el_clasificador(crear_agente):
    # Las reglas no la detectan; el clasificador sí (recall combinado)
    r = crear_agente().turno('prefiero no existir')
    assert r.accion == 'crisis'


def test_g3_crisis_con_imagen_alegre(crear_agente):
    vision = ImagenFalsa('alegría', 0.99)
    r = crear_agente(vision).turno('quiero quitarme la vida', imagen=FOTO, consentimiento=True)
    assert r.accion == 'crisis' and r.expresion is None
    assert vision.llamadas == 0  # la imagen ni siquiera se procesa


def test_g4_imagen_triste_sin_crisis(crear_agente):
    r = crear_agente(ImagenFalsa('tristeza', 0.9)).turno('estoy muy estresado con las entregas', imagen=FOTO, consentimiento=True)
    assert r.accion == 'responder' and 'imagen' in tipos(r) and 'crisis' not in tipos(r)
    frase = next(s['contenido'] for s in r.respuesta if s['tipo'] == 'imagen')
    assert 'puedo equivocarme' in frase  # lenguaje de posibilidad


def test_g5_imagen_sin_consentimiento(crear_agente):
    vision = ImagenFalsa()
    r = crear_agente(vision).turno('estoy muy estresado con las entregas', imagen=FOTO, consentimiento=False)
    assert vision.llamadas == 0 and r.expresion is None


def test_g6_texto_ambiguo_pide_aclaracion(crear_agente):
    r = crear_agente().turno('asdf qwerty')
    assert r.accion == 'aclaracion' and r.estado['aclaraciones'] == 1


def test_g6_baja_confianza_con_imagen_no_la_comenta(crear_agente):
    vision = ImagenFalsa()
    r = crear_agente(vision).turno('asdf qwerty', imagen=FOTO, consentimiento=True)
    assert r.accion == 'aclaracion' and vision.llamadas == 0


def test_g7_contradiccion_texto_imagen(crear_agente):
    r = crear_agente(ImagenFalsa('alegría', 0.95)).turno('estoy muy estresado con las entregas', imagen=FOTO, consentimiento=True)
    frase = next(s['contenido'] for s in r.respuesta if s['tipo'] == 'imagen')
    assert r.intencion == 'estres_academico'  # prevalece el texto
    assert 'lo que me escribes cuenta más' in frase


def test_g8_regla_de_pausa(crear_agente):
    for duda in ['mmm', 'mmm no sé', 'no sé', 'ni idea', 'hmmm']:
        r = crear_agente().turno(duda)
        assert r.accion == 'pausa', duda


def test_g8_la_pausa_no_tapa_una_crisis_por_reglas(crear_agente):
    assert crear_agente().turno('no sé, quiero morir').accion == 'crisis'


def test_g9_memoria_canaliza_sin_repetirse(crear_agente):
    agente, estado, ofertas = crear_agente(), {}, []
    for texto in ['estoy muy estresado con las entregas', 'tengo ansiedad por el examen', 'sigo muy estresado con las tareas', 'otra vez estresado con la escuela']:
        r = agente.turno(texto, estado)
        estado = r.estado
        ofertas += [s['contenido'] for s in r.respuesta if s['tipo'] == 'oferta']
    # Tras 3 intenciones emocionales se ofrece la cita una sola vez; la respiración ya la ofreció la respuesta de ansiedad
    assert len(ofertas) == 1 and 'orientación' in ofertas[0]
    assert set(estado['ofertas']) == {'respiracion', 'cita'}


def test_g9_no_repite_el_mismo_parrafo(crear_agente):
    agente, estado, textos = crear_agente(), {}, []
    for texto in ['estoy muy estresado con las entregas', 'sigo muy estresado', 'la escuela me tiene muy estresado']:
        r = agente.turno(texto, estado)
        estado = r.estado
        textos.append(r.respuesta[0]['contenido'])
    assert len(set(textos)) == 3


def test_g10_fuera_de_dominio_reorienta(crear_agente):
    for texto in ['¿quién ganó el partido?', 'recomiéndame una película', 'cómo hago una pizza']:
        r = crear_agente().turno(texto)
        assert r.accion != 'crisis'  # antes «¿quién ganó el partido?» caía en crisis por un solo término
        assert r.intencion in ('otro_tema', 'fallback'), texto


# ---------------------------------------------------------------- seguimiento de ofertas
def test_si_acepta_la_oferta_de_la_respuesta(crear_agente):
    agente = crear_agente()
    r = agente.turno('tengo mucha ansiedad por el examen')
    assert r.estado['oferta_pendiente'] == 'tecnica_respiracion'
    for afirmacion in ['sí, por favor', 'siii', 'ok', 'va', 'claro que sí']:
        r2 = agente.turno(afirmacion, r.estado)
        assert r2.intencion == 'tecnica_respiracion', afirmacion


def test_no_rechaza_la_oferta_sin_pausa(crear_agente):
    agente = crear_agente()
    r = agente.turno('tengo mucha ansiedad por el examen')
    for negacion in ['no', 'no gracias', 'ahorita no', 'mejor no']:
        r2 = agente.turno(negacion, r.estado)
        assert r2.accion == 'rechazo_oferta' and r2.estado['oferta_pendiente'] is None, negacion


def test_la_oferta_solo_dura_un_turno(crear_agente):
    agente = crear_agente()
    r = agente.turno('tengo mucha ansiedad por el examen')
    r = agente.turno('hola', r.estado)
    r = agente.turno('sí', r.estado)
    assert r.accion == 'aclaracion'  # un «sí» sin contexto no se adivina


def test_si_tras_una_crisis_no_desactiva_nada(crear_agente):
    agente = crear_agente()
    r = agente.turno('tengo mucha ansiedad por el examen')
    assert agente.turno('sí, ya no quiero vivir', r.estado).accion == 'crisis'


# ---------------------------------------------------------------- robustez del texto
def test_crisis_por_palabra_exacta_no_por_raiz(crear_agente):
    # Las reglas comparaban por raíz: «matarme» y «mate», «morir» y «morado» compartían raíz
    for texto in ['tengo examen de mate y me siento fatal', 'la escuela me mata', 'compré un suéter morado']:
        assert crear_agente().turno(texto).accion != 'crisis', texto


@pytest.mark.xfail(reason='Limitación conocida: el clasificador asocia «lástima» con «me estoy lastimando» (crisis)', strict=True)
def test_lastima_no_es_crisis(crear_agente):
    assert crear_agente().turno('qué lástima que no fui').accion != 'crisis'


def test_faltas_de_ortografia_y_letras_alargadas(crear_agente):
    for texto, esperada in [('estoy estresadisimo', 'estres_academico'), ('holaaaa', 'saludo'), ('organisacion', 'organizacion_tiempo')]:
        assert crear_agente().turno(texto).intencion == esperada, texto


def test_senal_debil_de_crisis_pide_contar_mas(crear_agente, conocimiento):
    r = crear_agente().turno('nadie me entiende')
    assert r.accion in ('aclaracion', 'responder') and r.accion != 'crisis'
    if r.accion == 'aclaracion':
        assert r.respuesta[-1]['contenido'] == conocimiento.texto('aclaracion_emocional')


# ---------------------------------------------------------------- políticas
def test_dos_aclaraciones_seguidas_dan_lista_de_temas(crear_agente):
    agente = crear_agente()
    r1 = agente.turno('asdf')
    r2 = agente.turno('qwerty', r1.estado)
    assert r1.respuesta[-1]['contenido'] != r2.respuesta[-1]['contenido']
    assert 'orientación' in r2.respuesta[-1]['contenido']


def test_tras_crisis_se_anteponen_recursos(crear_agente):
    agente = crear_agente()
    r = agente.turno('ya no quiero vivir')
    r = agente.turno('hola', r.estado)
    assert tipos(r)[0] == 'recursos'


def test_compartir_imagen_sin_imagen_la_pide_y_espera(crear_agente):
    agente, vision = None, ImagenFalsa('neutral', 0.9)
    agente = crear_agente(vision)
    r = agente.turno('te paso una foto')
    assert r.accion == 'pedir_imagen' and r.estado['esperando_imagen'] is True
    r = agente.turno('aquí está', r.estado, imagen=FOTO, consentimiento=True)
    assert vision.llamadas == 1 and r.estado['esperando_imagen'] is False


def test_imagen_baja_confianza_avisa(crear_agente, conocimiento):
    r = crear_agente(ImagenFalsa('tristeza', 0.3)).turno('estoy muy estresado con las entregas', imagen=FOTO, consentimiento=True)
    imagen = [s['contenido'] for s in r.respuesta if s['tipo'] == 'imagen']
    assert imagen == [conocimiento.vision['aviso_baja_confianza']]


def test_saludo_con_imagen_no_la_comenta(crear_agente):
    vision = ImagenFalsa()
    crear_agente(vision).turno('hola', imagen=FOTO, consentimiento=True)
    assert vision.llamadas == 0


def test_es_pausa():
    palabras = ['mmm', 'no', 'se', 'ni', 'idea']
    assert reactiva.es_pausa('Mmm... no sé', palabras, 5)
    assert not reactiva.es_pausa('no sé qué hacer con el examen', palabras, 5)
    assert not reactiva.es_pausa('', palabras, 5)


def test_estado_se_sanea():
    e = EstadoSesion.desde_dict(
        {'intenciones': ['saludo', 'inventada', 3], 'aclaraciones': 999, 'ofertas': ['cita', 'x'], 'crisis_mostrada': 'si'},
        {'saludo'}, memoria=5,
    )
    assert e.intenciones == ['saludo'] and e.aclaraciones == 10 and e.ofertas == ['cita'] and e.crisis_mostrada is False
    e = EstadoSesion.desde_dict({'oferta_pendiente': 'inventada', 'vistas': {'saludo': 2, 'x': 1, 'despedida': -3}}, {'saludo', 'despedida'}, 5)
    assert e.oferta_pendiente is None and e.vistas == {'saludo': 2}
    assert EstadoSesion.desde_dict('basura', set(), 5) == EstadoSesion()


def test_estado_no_guarda_texto(crear_agente):
    r = crear_agente().turno('estoy muy estresado con las entregas')
    assert 'estresado' not in str(r.estado)
