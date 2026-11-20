# Registro de cambios

## Proyecto final (noviembre de 2026)

### Estructura
- Repositorio dividido en `app/` (interfaz Streamlit), `api/` (Flask) y `modelo/` (`agente/`, `nlp/`, `vision/`, `conocimiento/`, `entrenamiento/`).
- El integrador del Avance 2 se sustituye por el agente híbrido (`modelo/agente/`).
- Requisitos separados: `requirements.txt` (interfaz), `requirements-api.txt` (API y modelos), `requirements-dev.txt` (todo + pruebas).

### Modelo de texto
- Corpus de 410 a 791 ejemplos; intenciones nuevas `animo_bajo` y `otro_tema` (15 en total).
- Representación de palabras + n-gramas de caracteres; F1 macro en validación cruzada de 0,762 a 0,826.
- Umbral de intención de 0,35 a 0,25; crisis por el clasificador con confianza ≥ 0,30 y ≥ 2 términos conocidos.
- Reglas de crisis por palabra exacta (antes por raíz) y nuevas frases de desesperanza y autolesión.
- Conjunto externo de 83 mensajes y script de evaluación (`evaluar_externo.py`).

### Agente
- Capa reactiva (crisis, pausa, consentimiento, baja confianza) y deliberativa (ofertas, lista de temas, recursos tras crisis).
- Respuestas con 2–3 variantes que rotan; ofertas con seguimiento («Sí, por favor» / «No, gracias») y acción `rechazo_oferta`.
- Segmento `recursos`; estado de sesión saneado en cada turno.
- Base de conocimiento `reglas.json` 2.2.0.

### API
- Rutas `/salud`, `/intencion`, `/imagen`, `/chat`, `/metricas`; clave por cabecera; formato de error único.
- Límite de frecuencia por sesión (20/min) y global (120/min); registros JSON con lista blanca; métricas con percentiles.
- Degradación segura sin modelo visual o de texto; tiempo máximo de 5 s para la visión.

### Interfaz
- Aviso inicial, banner de ayuda fijo, respuestas rápidas, escritura progresiva, panel lateral de análisis.
- Imagen desde el campo del chat o con el botón «Tomar foto», con consentimiento en un cuadro aparte.
- Aviso explícito cuando la respuesta tarda más de 6 s.
- Detección local de crisis si la API no responde; modo demostración sin API.

### Pruebas y mediciones
- 58 pruebas automáticas + 1 limitación conocida (`xfail`).
- `scripts/ejecutar_casos.py` (casos A, G y E con resultados observados) y `scripts/medir_desempeno.py` (latencia, memoria y carga).

## Avance 2
- Clasificador SVM + TF-IDF (13 intenciones, 410 ejemplos) y EfficientNet-B0 sobre FER-2013, unidos por un integrador reactivo.
