# Guía de despliegue

## Topología y costo

| Pieza | Dónde corre | Costo |
|---|---|---|
| Interfaz (`app/`) | Streamlit Community Cloud | Gratis |
| API y modelos (`api/`, `modelo/`) | Equipo local con Waitress | Gratis (el equipo debe seguir encendido y conectado) |
| Puente público | Cloudflare Quick Tunnel (`trycloudflare.com`) | Gratis, sin cuenta |
| Código | GitHub | Gratis |

Con esta configuración el despliegue cuesta $0. Una dirección fija para la API exigiría un túnel con
nombre (cuenta gratuita de Cloudflare) y un dominio propio, que sí tiene costo anual. Los límites de
las plataformas pueden cambiar: verifícalos en su documentación vigente.

## 1. Preparar el equipo local

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-api.txt
cp .env.example .env            # y cambia las dos claves por valores largos y aleatorios
```

Para generar claves: `python -c "import secrets; print(secrets.token_urlsafe(32))"`.
Comprueba que existan `modelos/intenciones.joblib` y `modelos/vision_efficientnet_b0.pt`.

## 2. Arrancar la API

```bash
set -a && source .env && set +a
python -m api.servidor          # http://127.0.0.1:8000/api/v1/salud → "estado": "listo"
```

El servidor se niega a arrancar sin `DOKI_API_KEY`. Escucha solo en `127.0.0.1`: el túnel es la única entrada.

## 3. Abrir el túnel

```bash
brew install cloudflared                      # macOS; en otros sistemas, ver la documentación de Cloudflare
cloudflared tunnel --url http://localhost:8000
```

Copia la dirección `https://….trycloudflare.com` que imprime y comprueba `https://….trycloudflare.com/api/v1/salud`.
Para que el equipo no se suspenda durante la demostración: `caffeinate -dims` (macOS).

## 4. Publicar la interfaz en Streamlit Community Cloud

1. Entra a <https://share.streamlit.io> con la cuenta de GitHub y elige **Create app**.
2. Repositorio `Diego-code-ctrl/chatbot_BER_DOKI`, rama `main`, archivo principal `app/main.py`.
3. En **Advanced settings**: Python 3.12 y, en **Secrets**:

   ```toml
   API_URL = "https://….trycloudflare.com"
   API_KEY = "el mismo valor que DOKI_API_KEY"
   ```

4. **Deploy.** La plataforma instala solo `requirements.txt` (`streamlit` y `requests`).

Sin `API_URL` la interfaz arranca en modo demostración, con frases fijas.

## Operación

| Situación | Qué hacer |
|---|---|
| Se reinició el túnel | La dirección cambia: actualiza `API_URL` en *Settings → Secrets* de la app |
| La interfaz dice «DOKi no está disponible» | Revisa que la API y el túnel sigan activos y abre `/salud` desde el navegador |
| `/salud` responde 503 | Falta el modelo de texto: `python -m modelo.entrenamiento.entrenar_intenciones` |
| La imagen nunca se comenta | `/salud` muestra `"imagen": false`: falta `modelos/vision_efficientnet_b0.pt` o PyTorch |
| Aparece «Hay muchas solicitudes» | Se alcanzó el límite (20/min por sesión, 120/min en total); ajusta `DOKI_LIMITE_*` si hace falta |
| Sospecha de clave filtrada | Cambia `DOKI_API_KEY` en `.env`, reinicia la API y actualiza el secreto en Streamlit |
| La app de Streamlit «se durmió» | Ábrela y pulsa el botón para despertarla; tarda unos segundos |

Registros: `logs/eventos.jsonl` (solo metadatos). Métricas: `GET /api/v1/metricas` con `X-Admin-Key`.

## Limitaciones del plan

Es un despliegue de demostración: depende de un equipo personal y de un túnel sin garantía de
disponibilidad. Un servicio real exigiría alojar la API en un servidor con disponibilidad garantizada,
en una región y bajo un contrato que respeten la normativa de protección de datos aplicable.
