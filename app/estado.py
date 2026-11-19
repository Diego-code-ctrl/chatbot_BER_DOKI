"""Estado de la sesión del navegador: historial, memoria del agente y control del panel de imagen.
Vive solo mientras dura la sesión; no se guarda en ningún servidor."""
import uuid

import streamlit as st


def iniciar() -> None:
    valores = {
        'id_sesion': uuid.uuid4().hex,  # aleatorio, sin datos personales; solo para el límite de frecuencia
        'aviso_aceptado': False,
        'mensajes': [],          # [{'rol', 'segmentos', 'error'}]
        'estado_agente': {},     # memoria devuelta por la API en el turno anterior
        'meta_ultimo': None,     # análisis del último turno, para el panel lateral
        'envio_listo': None,     # envío con imagen confirmado en el diálogo de consentimiento
        'ultimo_envio': None,    # solicitud guardada para el botón «Reintentar»
    }
    for k, v in valores.items():
        st.session_state.setdefault(k, v)


def borrar_conversacion() -> None:
    st.session_state.mensajes = []
    st.session_state.estado_agente = {}
    st.session_state.ultimo_envio = None
    st.session_state.meta_ultimo = None
    st.session_state.envio_listo = None
