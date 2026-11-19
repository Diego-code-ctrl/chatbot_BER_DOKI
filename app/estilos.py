"""CSS de la interfaz: minimalista, un solo color de acento, contraste alto y una columna.
Paleta: papel cálido (#F7F6F2), tinta verdosa (#1D2521), acento salvia (#2F6F62); ámbar solo para ayuda de crisis."""
import streamlit as st

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
:root {
  --papel: #F7F6F2; --tinta: #1D2521; --suave: #5E6A64; --linea: #E2DFD6;
  --acento: #2F6F62; --acento-claro: #E3EFEA; --burbuja: #ECEAE2;
  --crisis-fondo: #FFF3E6; --crisis: #A63D00; --error-fondo: #FBECEA; --error: #A32A21;
}
html, body, [class*="css"], .stApp { font-family: 'Inter', system-ui, sans-serif; }
.stApp { background: radial-gradient(1200px 500px at 50% -10%, #E6F0EB 0%, var(--papel) 60%); }
.block-container { padding-top: 4rem; padding-bottom: 7rem; max-width: 720px; }
header[data-testid="stHeader"] { background: transparent; }
footer, #MainMenu { visibility: hidden; }

/* Banner de ayuda: discreto pero siempre visible */
.doki-ayuda {
  position: fixed; top: 0; left: 0; right: 0; z-index: 999991; text-align: center;
  background: rgba(255,255,255,.85); backdrop-filter: blur(8px); border-bottom: 1px solid var(--linea);
  color: var(--tinta); padding: .5rem .75rem; font-size: .85rem; line-height: 1.3;
}
.doki-ayuda a { color: var(--acento); font-weight: 600; text-decoration: none; white-space: nowrap; border-bottom: 1px solid currentColor; }
.doki-ayuda a:focus-visible { outline: 3px solid var(--acento); outline-offset: 2px; border-radius: 4px; }

/* Marca y portada */
.doki-marca { font-weight: 700; font-size: 1.15rem; letter-spacing: -.01em; color: var(--tinta); display: flex; align-items: center; gap: .5rem; }
.doki-marca::before { content: ''; width: .7rem; height: .7rem; border-radius: 50%; background: linear-gradient(135deg, #5FB59F, var(--acento)); }
.doki-hero { text-align: center; padding: 3.5rem 0 1.5rem; }
.doki-hero h1 { font-size: clamp(2rem, 6vw, 2.9rem); font-weight: 700; letter-spacing: -.03em; line-height: 1.1; margin: 0 0 .75rem;
  background: linear-gradient(120deg, #1D2521 20%, var(--acento) 90%); -webkit-background-clip: text; background-clip: text; color: transparent; }
.doki-hero p { color: var(--suave); font-size: 1.05rem; margin: 0; }

/* Mensajes: DOKi sin burbuja, la persona en burbuja a la derecha, sin avatares */
[data-testid="stChatMessage"] { background: transparent; padding: .35rem 0; gap: 0; }
[data-testid="stChatMessageAvatarUser"], [data-testid="stChatMessageAvatarAssistant"] { display: none; }
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) { flex-direction: row-reverse; }
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) > div:last-child {
  background: var(--burbuja); border-radius: 18px 18px 4px 18px; padding: .6rem 1rem; max-width: 85%; flex: 0 1 auto;
}
[data-testid="stChatMessageContent"] { font-size: 1.02rem; line-height: 1.65; }

/* Etiquetas y notas */
.doki-etiqueta { font-size: .72rem; font-weight: 600; letter-spacing: .08em; text-transform: uppercase; margin-bottom: .3rem; }
.doki-crisis { background: var(--crisis-fondo); border: 1px solid #F0CFAE; border-left: 5px solid var(--crisis); border-radius: 14px; padding: .85rem 1.1rem; color: #3B1A00; margin: .5rem 0; }
.doki-crisis .doki-etiqueta { color: var(--crisis); }
.doki-nota { background: var(--acento-claro); border-radius: 14px; padding: .7rem 1rem; color: #17382F; margin: .5rem 0; }
.doki-nota .doki-etiqueta { color: var(--acento); }
.doki-error { background: var(--error-fondo); border-radius: 14px; padding: .8rem 1.1rem; color: #471410; margin: .5rem 0; }
.doki-error .doki-etiqueta { color: var(--error); }
/* Portada (aviso inicial): un solo bloque centrado, angosto para leerse bien */
.st-key-aviso { max-width: 560px; margin: 1.5rem auto 0; gap: .75rem; }
.doki-portada { text-align: center; }
.doki-portada .doki-marca { justify-content: center; margin-bottom: 1.4rem; }
.doki-portada h1 { font-size: clamp(1.9rem, 6vw, 2.6rem); font-weight: 700; letter-spacing: -.03em; line-height: 1.12; margin: 0 0 .8rem; padding: 0;
  background: linear-gradient(120deg, #1D2521 25%, var(--acento) 95%); -webkit-background-clip: text; background-clip: text; color: transparent; }
.doki-sub { color: var(--suave); font-size: 1.02rem; line-height: 1.55; max-width: 30rem; margin: 0 auto 1.6rem; }
.doki-puntos { list-style: none; padding: 0; margin: 0 0 1rem; display: grid; grid-template-columns: 1fr 1fr; gap: .75rem; text-align: left; }
.doki-puntos li { display: flex; gap: .75rem; align-items: flex-start; margin: 0; padding: .95rem 1rem;
  background: rgba(255,255,255,.75); border: 1px solid var(--linea); border-radius: 16px; }
.doki-puntos strong { display: block; font-size: .93rem; color: var(--tinta); margin-bottom: .2rem; }
.doki-puntos p { margin: 0; font-size: .86rem; line-height: 1.45; color: var(--suave); }
.doki-icono { flex: none; display: grid; place-items: center; width: 2.1rem; height: 2.1rem; border-radius: 10px; background: var(--acento-claro); color: var(--acento); }
.doki-urgente { text-align: left; font-size: .9rem; line-height: 1.5; color: #3B1A00; background: var(--crisis-fondo);
  border: 1px solid #F0CFAE; border-radius: 14px; padding: .8rem 1rem; }
.doki-urgente strong { display: block; color: var(--crisis); }
.doki-urgente a { color: var(--crisis); font-weight: 600; white-space: nowrap; }
.st-key-aviso .stButton > button { padding: .7rem 1rem; font-size: 1rem; }
.st-key-aviso [data-testid="stExpander"] { background: transparent; border: none; }
.st-key-aviso [data-testid="stExpander"] summary { justify-content: center; font-size: .88rem; }
@media (max-width: 560px) { .doki-puntos { grid-template-columns: 1fr; } }

/* Respuestas rápidas: píldoras compactas que se acomodan en varias líneas */
.st-key-rapidas { flex-wrap: wrap; gap: .45rem; }
.st-key-rapidas .stButton > button { padding: .3rem .9rem; min-height: 0; font-size: .9rem; background: rgba(255,255,255,.85); }

/* Controles */
.stButton > button { border-radius: 999px; border: 1px solid var(--linea); background: #fff; color: var(--tinta); font-weight: 500; transition: all .15s ease; }
.stButton > button:hover { border-color: var(--acento); color: var(--acento); }
.stButton > button[kind="primary"] { background: var(--acento); border-color: var(--acento); color: #fff; }
.stButton > button[kind="primary"]:hover { background: #255A4F; color: #fff; }
button:focus-visible, [role="switch"]:focus-visible { outline: 3px solid var(--acento) !important; outline-offset: 2px; }
[data-testid="stChatInput"] { border-radius: 999px; border: 1px solid var(--linea); box-shadow: 0 8px 24px -14px rgba(29,37,33,.4); background: #fff; }
[data-testid="stBottom"] > div { background: transparent; }
[data-testid="stExpander"] { border: 1px solid var(--linea); border-radius: 14px; background: rgba(255,255,255,.6); }
[data-testid="stExpander"] summary { font-size: .92rem; color: var(--suave); }
</style>
"""


def aplicar() -> None:
    st.markdown(CSS, unsafe_allow_html=True)
