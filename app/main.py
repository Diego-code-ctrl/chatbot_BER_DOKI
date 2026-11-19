"""Interfaz Streamlit de DOKi. Arranque: streamlit run app/main.py
No contiene modelos ni decide nada sobre el contenido de las respuestas: captura, valida, llama a la API y muestra."""
import streamlit as st

import componentes as ui
import crisis_local
import estado
import estilos
from cliente_api import ClienteApi, ErrorApi
from cliente_demo import ClienteDemo
from config import FORMATOS_IMAGEN, MAX_BYTES_IMAGEN, MAX_CARACTERES, cargar_ajustes

st.set_page_config(page_title='DOKi', page_icon='💬', layout='centered', initial_sidebar_state='collapsed')
estilos.aplicar()
estado.iniciar()
ajustes = cargar_ajustes()


@st.cache_data(ttl=30, show_spinner=False)
def _salud(url: str, clave: str) -> str:
    try:
        return 'disponible' if ClienteApi(url, clave).salud().get('estado') == 'listo' else 'no_listo'
    except ErrorApi:
        return 'caida'


def cliente():
    return ClienteDemo() if ajustes.modo_demo else ClienteApi(ajustes.api_url, ajustes.api_key, st.session_state.id_sesion)


def turno(envio: dict) -> None:
    """Ejecuta un turno y agrega la respuesta (o un error controlado) al historial. No reintenta solo."""
    st.session_state.ultimo_envio = envio
    try:
        with st.chat_message('assistant'):
            with st.spinner('DOKi está escribiendo…'):
                r = cliente().chat(envio['texto'], st.session_state.estado_agente, envio['imagen'], envio['consentimiento'])
            ui.mostrar_segmentos(r['respuesta'], animar=True)  # escritura progresiva
        st.session_state.estado_agente = r.get('estado', {})
        st.session_state.mensajes.append({'rol': 'assistant', 'segmentos': r['respuesta']})
        st.session_state.meta_ultimo = r
    except ErrorApi as e:
        if crisis_local.parece_crisis(envio['texto']):
            # La API no respondió y el mensaje parece de crisis: el protocolo va primero, sin esperar
            st.session_state.mensajes.append({'rol': 'assistant', 'segmentos': [{'tipo': 'crisis', 'contenido': crisis_local.PROTOCOLO_LOCAL}]})
        st.session_state.mensajes.append({'rol': 'assistant', 'error': ui.mensaje_de_error(e)})


ui.banner_ayuda()

if not st.session_state.aviso_aceptado:
    if ui.aviso_inicial():
        st.session_state.aviso_aceptado = True
        st.rerun()
    st.stop()

# --- Cabecera y controles
izq, der = st.columns([3, 2], vertical_alignment='center')
izq.markdown('<div class="doki-marca">DOKi</div>', unsafe_allow_html=True)
if der.button('Borrar conversación'):
    estado.borrar_conversacion()
    st.rerun()

with st.sidebar:
    ui.panel_analisis(st.session_state.meta_ultimo)
    st.divider()
    st.header('Sobre DOKi')
    st.markdown('Asistente automatizado de orientación. No sustituye a un profesional.')
    if ajustes.modo_demo:
        st.warning('Modo demostración: la interfaz responde con frases fijas porque no hay API configurada (`API_URL`).')
    else:
        st.caption({'disponible': 'Conectado al asistente.', 'no_listo': 'El asistente se está iniciando.', 'caida': 'Sin conexión con el asistente.'}[_salud(ajustes.api_url, ajustes.api_key)])
    if st.button('Volver al aviso inicial'):
        st.session_state.aviso_aceptado = False
        st.rerun()

if ajustes.modo_demo:
    st.caption('Modo demostración · respuestas de ejemplo, sin modelos')

if not ajustes.modo_demo and _salud(ajustes.api_url, ajustes.api_key) == 'caida':
    st.markdown(
        '<div class="doki-error" role="alert"><div class="doki-etiqueta">Aviso</div>'
        'DOKi no está disponible ahora. Los números de ayuda de arriba siguen funcionando.</div>',
        unsafe_allow_html=True,
    )

# --- Historial
rapida = None
if not st.session_state.mensajes:
    st.markdown(
        '<div class="doki-hero"><h1>Hola, soy DOKi</h1>'
        '<p>Un espacio tranquilo para hablar de estrés, ansiedad, sueño o cómo organizarte.</p></div>',
        unsafe_allow_html=True,
    )
    rapida = ui.respuestas_rapidas()

reintentar = False
msgs = st.session_state.mensajes
for i, m in enumerate(msgs):
    if m['rol'] == 'user':
        with st.chat_message('user'):
            st.markdown(m['texto'])
            if m.get('con_imagen'):
                st.caption('Se adjuntó una imagen')
    else:
        reintentar = ui.mostrar_mensaje(m, es_ultimo=(i == len(msgs) - 1)) or reintentar

if reintentar and st.session_state.ultimo_envio:
    msgs.pop()  # quita el aviso de error y repite el mismo turno
    turno(st.session_state.ultimo_envio)
    st.rerun()

# --- Entrada
ultimo = msgs[-1] if msgs else None
meta = st.session_state.meta_ultimo or {}
if ultimo and ultimo['rol'] == 'assistant' and not ultimo.get('error'):
    if meta.get('accion') == 'aclaracion':
        rapida = ui.respuestas_rapidas()
    elif (meta.get('estado') or {}).get('oferta_pendiente'):
        rapida = ui.respuestas_oferta()

# El clip del propio campo adjunta la imagen; el consentimiento se pide al enviar
entrada = st.chat_input(
    'Escribe tu mensaje…', max_chars=MAX_CARACTERES, accept_file=True,
    file_type=['jpg', 'jpeg', 'png'], max_upload_size=MAX_BYTES_IMAGEN // (1024 * 1024),
)
envio = st.session_state.envio_listo
st.session_state.envio_listo = None

if entrada and entrada.files:
    texto = (entrada.text or '').strip() or 'Te comparto una imagen'
    archivo = entrada.files[0]
    if archivo.size > MAX_BYTES_IMAGEN or archivo.type not in FORMATOS_IMAGEN:
        st.warning('La imagen debe ser JPEG o PNG de hasta 5 MB. Puedes continuar solo con texto.')
    else:
        ui.dialogo_consentimiento(texto, archivo)
elif entrada and entrada.text or rapida:
    envio = {'texto': entrada.text if entrada and entrada.text else rapida, 'imagen': None, 'consentimiento': False}

if envio:
    msgs.append({'rol': 'user', 'texto': envio['texto'], 'con_imagen': envio['imagen'] is not None})
    with st.chat_message('user'):
        st.markdown(envio['texto'])
    turno(envio)
    st.rerun()
