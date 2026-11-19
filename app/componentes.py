"""Piezas visuales reutilizables de la interfaz"""
from html import escape

import re
import time

import streamlit as st

from cliente_api import ErrorApi
from config import PAUSA_PALABRA, PAUSA_PUNTUACION, EMERGENCIAS, LINEA_DE_LA_VIDA, RESPUESTAS_OFERTA, TEMAS_RAPIDOS
from cliente_api import Imagen


def _tel(numero: str) -> str:
    return numero.replace(' ', '')


def banner_ayuda() -> None:
    (n1, t1), (n2, t2) = LINEA_DE_LA_VIDA, EMERGENCIAS
    st.markdown(
        f'<div class="doki-ayuda" role="region" aria-label="Ayuda inmediata">'
        f'¿Necesitas ayuda ahora? <a href="tel:{_tel(t1)}">{n1} {t1}</a> · '
        f'<a href="tel:{_tel(t2)}">{n2} {t2}</a></div>',
        unsafe_allow_html=True,
    )


# Iconos de trazo (24 × 24), heredan el color del texto
_ICONOS = {
    'asistente': '<rect x="4" y="7" width="16" height="12" rx="4"/><path d="M12 7V4M9 13h.01M15 13h.01"/>',
    'brujula': '<circle cx="12" cy="12" r="9"/><path d="m15.5 8.5-2 5-5 2 2-5z"/>',
    'imagen': '<rect x="3" y="5" width="18" height="14" rx="3"/><circle cx="9" cy="10" r="1.5"/><path d="m21 16-5-5-8 8"/>',
    'candado': '<rect x="5" y="11" width="14" height="9" rx="2.5"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/>',
}

_PUNTOS = [
    ('asistente', 'Soy un asistente automatizado', 'No soy una persona ni un profesional de la salud, y no sustituyo la atención psicológica.'),
    ('brujula', 'Oriento, no diagnostico', 'No doy diagnósticos ni recomiendo medicamentos: te ayudo a encontrar a quién acudir.'),
    ('imagen', 'Tu imagen es opcional', 'Solo la analizo si me das permiso cada vez. Puedes usar DOKi completo sin ella.'),
    ('candado', 'No guardo tu conversación', 'Tus mensajes e imágenes no se almacenan; la conversación vive solo en este navegador.'),
]


def _icono(nombre: str) -> str:
    return (
        '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.8" '
        f'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{_ICONOS[nombre]}</svg>'
    )


def aviso_inicial() -> bool:
    """Portada con el aviso inicial (sección 6.1). Devuelve True cuando la persona acepta continuar"""
    (n1, t1), (n2, t2) = LINEA_DE_LA_VIDA, EMERGENCIAS
    puntos = ''.join(
        f'<li><span class="doki-icono">{_icono(i)}</span><div><strong>{titulo}</strong><p>{texto}</p></div></li>'
        for i, titulo, texto in _PUNTOS
    )
    with st.container(key='aviso'):
        st.markdown(
            f'''<div class="doki-portada">
              <div class="doki-marca">DOKi</div>
              <h1>Un espacio para hablar,<br>sin juicios</h1>
              <p class="doki-sub">Te escucho y te oriento sobre estrés, ansiedad, sueño u organización.
                Antes de empezar, esto es lo que conviene que sepas.</p>
              <ul class="doki-puntos">{puntos}</ul>
              <div class="doki-urgente" role="note">
                <strong>¿Estás en peligro o piensas en hacerte daño?</strong>
                Llama ahora a la <a href="tel:{_tel(t1)}">{n1} · {t1}</a> o al <a href="tel:{_tel(t2)}">{t2}</a>.
              </div>
            </div>''',
            unsafe_allow_html=True,
        )
        aceptado = st.button('Entiendo, empezar', type='primary', use_container_width=True)
        with st.expander('¿Qué pasa con mis datos?'):
            st.markdown(
                'Tu texto (y tu imagen, si la compartes) viaja por servicios de terceros hasta el equipo que lo procesa: '
                'la plataforma que aloja esta página, que opera en Estados Unidos, y una red de túneles. Se procesa en '
                'memoria y se descarta al terminar la respuesta. El registro técnico guarda solo datos como la hora y la '
                'intención detectada, nunca el contenido.\n\n'
                '*Borrador del aviso de privacidad: debe revisarse con el área jurídica antes de un uso real.*'
            )
    return aceptado


ETIQUETAS_ACCION = {
    'responder': 'Responder a tu tema',
    'aclaracion': 'Pedir que me aclares',
    'pausa': 'Darte tiempo',
    'crisis': 'Mostrar ayuda inmediata',
    'pedir_imagen': 'Pedir tu imagen',
    'despedida': 'Despedirme',
    'error_modelo': 'Darte los recursos de ayuda (no pude analizar tu mensaje)',
    'rechazo_oferta': 'Respetar que no quisieras la sugerencia',
}


def _flujo(texto: str):
    """Entrega el texto palabra por palabra, como escriben los asistentes actuales"""
    for pedazo in re.findall(r'\S+\s*|\s+', texto):
        yield pedazo
        time.sleep(PAUSA_PALABRA + (PAUSA_PUNTUACION if pedazo.strip()[-1:] in '.,;:?!' else 0))


def _segmento(seg: dict, animar: bool = False) -> None:
    tipo, contenido = seg.get('tipo', 'texto'), escape(seg.get('contenido', ''))
    if tipo == 'crisis':
        st.markdown(f'<div class="doki-crisis" role="alert"><div class="doki-etiqueta">Ayuda inmediata</div>{contenido}</div>', unsafe_allow_html=True)
    elif tipo == 'imagen':
        st.markdown(f'<div class="doki-nota"><div class="doki-etiqueta">Sobre tu imagen</div>{contenido}</div>', unsafe_allow_html=True)
    elif tipo == 'recursos':
        st.markdown(f'<div class="doki-nota"><div class="doki-etiqueta">Ayuda disponible</div>{contenido}</div>', unsafe_allow_html=True)
    elif tipo == 'oferta':
        st.markdown(f'<div class="doki-nota"><div class="doki-etiqueta">Sugerencia</div>{contenido}</div>', unsafe_allow_html=True)
    elif animar:
        st.write_stream(_flujo(seg.get('contenido', '')))
    else:
        st.markdown(seg.get('contenido', ''))


def mostrar_segmentos(segmentos: list[dict], animar: bool = False) -> None:
    for seg in segmentos:
        _segmento(seg, animar and seg.get('tipo', 'texto') == 'texto')
        if animar:
            time.sleep(0.15)


def mensaje_de_error(e: ErrorApi) -> str:
    """Lenguaje llano, sin códigos técnicos, y sin explicar el motivo de un 401"""
    if e.http == 400:
        return 'No pude leer tu mensaje. Revisa que no esté vacío ni supere los 500 caracteres.'
    if e.http in (413, 415):
        return 'La imagen no se pudo usar: debe ser JPEG o PNG de hasta 5 MB. Puedes continuar solo con texto.'
    if e.http == 429:
        return 'Hay muchas solicitudes en este momento. Espera unos segundos e inténtalo de nuevo.'
    return 'DOKi no está disponible en este momento.'


def mostrar_mensaje(m: dict, es_ultimo: bool) -> bool:
    """Dibuja un mensaje del historial. Devuelve True si se pulsó «Reintentar»"""
    reintentar = False
    avatar = None
    with st.chat_message(m['rol'], avatar=avatar):
        if m.get('error'):
            st.markdown(
                f'<div class="doki-error" role="alert"><div class="doki-etiqueta">Aviso</div>{escape(m["error"])} '
                f'Si necesitas ayuda ahora, usa los números de arriba.</div>',
                unsafe_allow_html=True,
            )
            if es_ultimo:
                reintentar = st.button('Reintentar', key='reintentar')
        else:
            mostrar_segmentos(m['segmentos'])
    return reintentar


def respuestas_oferta() -> str | None:
    return respuestas_rapidas(RESPUESTAS_OFERTA)


def respuestas_rapidas(opciones: list[str] | None = None) -> str | None:
    """Botones de respuesta rápida en una sola fila que se acomoda al ancho (pills)"""
    opciones = opciones or TEMAS_RAPIDOS
    with st.container(key='rapidas', horizontal=True):
        for opcion in opciones:
            if st.button(opcion, key=f'rapida_{opcion}'):
                return opcion
    return None


@st.dialog('¿Analizar tu imagen?')
def dialogo_consentimiento(texto: str, archivo) -> None:
    """Consentimiento explícito, pedido cada vez que se adjunta una imagen. Cerrar el diálogo equivale a no autorizar"""
    st.markdown(
        'DOKi puede comentar tu **expresión aparente**. La imagen se analiza solo ahora, '
        'no se guarda y es solo una hipótesis: tú sabes cómo te sientes.'
    )
    if st.button('Autorizar y enviar', type='primary', use_container_width=True):
        st.session_state.envio_listo = {'texto': texto, 'imagen': Imagen(archivo.getvalue(), archivo.name or 'foto.png', archivo.type), 'consentimiento': True}
        st.rerun()
    if st.button('Enviar sin la imagen', use_container_width=True):
        st.session_state.envio_listo = {'texto': texto, 'imagen': None, 'consentimiento': False}
        st.rerun()


def panel_analisis(meta: dict | None) -> None:
    """Cómo se interpretó el último mensaje; vive aparte (panel lateral) para no estorbar la conversación"""
    st.subheader('Cómo entendí tu mensaje')
    if not meta:
        st.caption('Aparecerá aquí después de tu primer mensaje.')
        return
    conf = meta.get('confianza_texto')
    st.markdown(
        f"- **Tema:** {meta.get('intencion', '—')}"
        + (f' ({conf:.0%} de confianza)' if isinstance(conf, (int, float)) else '')
        + f"\n- **Qué hice:** {ETIQUETAS_ACCION.get(meta.get('accion'), meta.get('accion', '—'))}"
    )
    if meta.get('expresion'):
        st.markdown(f"- **Imagen:** se usó; expresión aparente «{meta['expresion']}» ({meta['confianza_visual']:.0%}). Es solo una hipótesis.")
    else:
        st.markdown('- **Imagen:** no se usó.')
    st.caption(f"Solicitud {meta.get('id_solicitud', '—')} · versiones: {meta.get('version_modelos') or '—'}")
