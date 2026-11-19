# DOKi · asistente de orientación universitaria

Aplicación web con tres capas separadas. La interfaz no tiene modelos; la API es la única puerta de
entrada; el agente es el único que invoca a los modelos.

```
chatbot_BER_DOKI/
├── app/            Interfaz Streamlit. Solo habla con la API (o con un sustituto de demostración)
├── api/            API REST Flask: validación, autenticación, errores, registros, métricas, límites
├── modelo/
│   ├── agente/         agente híbrido: capa reactiva, capa deliberativa, estado de sesión
│   ├── nlp/            preprocesamiento, TF-IDF, clasificador de intenciones, reglas de crisis
│   ├── vision/         dataset FER-2013, arquitectura, inferencia y evaluación
│   ├── conocimiento/   reglas.json: respuestas, textos y parámetros del agente (versionado)
│   └── entrenamiento/  scripts de entrenamiento, evaluación y calibración
├── tests/          pruebas automáticas (casos de la sección 9)
├── datos/  modelos/  resultados/
├── requirements.txt        interfaz (lo lee Streamlit Community Cloud)
├── requirements-api.txt    API y modelos (equipo local)
└── requirements-dev.txt    todo lo anterior + pytest y Jupyter
```

## Entorno

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
```

Los artefactos `modelos/intenciones.joblib` y `modelos/vision_efficientnet_b0.pt` deben estar en el
repositorio (o en el equipo de la API). Si falta el de texto: `python -m modelo.entrenamiento.entrenar_intenciones`.

## Ejecutar

```bash
# API (Waitress, un proceso con hilos; los modelos se cargan una vez)
export DOKI_API_KEY=una-clave-larga DOKI_ADMIN_KEY=otra-clave
python -m api.servidor                      # http://127.0.0.1:8000/api/v1/salud

# Interfaz
cp .streamlit/secrets.toml.example .streamlit/secrets.toml   # API_URL y API_KEY
streamlit run app/main.py

# Consola del agente, sin API ni interfaz
python -m modelo.consola
```

Sin `API_URL`, la interfaz arranca en **modo demostración** (frases fijas, mismo contrato que la API).

## Modelo de texto

SVM lineal calibrada sobre **TF-IDF de palabras (uni y bigramas) + n-gramas de caracteres (2–4)**.
Los caracteres toleran faltas de ortografía y letras alargadas («estresadisimo», «holaaa»,
«organisacion»). 15 intenciones; corpus de 791 ejemplos (`datos/intenciones.csv`).

| | Avance 2 | Actual |
|---|---|---|
| Intenciones / ejemplos | 13 / 410 | 15 / 791 (+ `animo_bajo`, `otro_tema`) |
| F1 macro, validación cruzada | 0,762 | 0,83 |
| Aciertos del agente con mensajes nunca vistos (`datos/intenciones_externo.csv`, 83) | 78 % | **93 %** |
| Aclaraciones en esos mensajes | 8,4 % | 4,8 % |

Los resultados del Avance 2 se conservan en `resultados/avance2/` y `modelos/intenciones_avance2.joblib`.
Las particiones de prueba no son comparables entre versiones (el corpus cambió); la comparación
justa es el conjunto externo. **Cautela**: las frases nuevas y el conjunto externo se redactaron
con IA, como el corpus original; ninguno sustituye mensajes reales de estudiantes.

```bash
python -m modelo.entrenamiento.entrenar_intenciones   # entrena, elige por validación cruzada, calibra el umbral
python -m modelo.entrenamiento.evaluar_externo        # conjunto externo + calibración de la regla de crisis
```

## Agente

Cada turno: percepción → capa reactiva → visión → capa deliberativa → respuesta.

| Prioridad | Regla reactiva | Efecto |
|---|---|---|
| 1 | Crisis (reglas **o** clasificador) | Protocolo; se ignora la imagen; termina el turno |
| — | Respuesta a una oferta («sí, porfa», «no gracias») | Cumple o descarta lo que DOKi ofreció en el turno anterior |
| 2 | Pausa (el mensaje entero es una duda corta) | Respuesta paciente |
| 3 | Consentimiento | Sin imagen o sin permiso, el modelo visual no se ejecuta |
| 4 | Baja confianza, sin palabras conocidas y confianza < 0,5, o «crisis» rechazada por la regla 1 | Aclaración |

**Crisis.** Reglas por **palabra exacta** (antes por raíz: «matarme» coincidía con «mate» y
«la escuela me mata», «morir» con «morado») más patrones de frase (sentirse una carga,
desesperanza, no querer despertar, autolesión). El clasificador cuenta si su confianza es ≥ 0,30,
el mensaje tiene ≥ 2 términos conocidos y no es una duda ni un «sí»/«no» breve. Recall combinado
en validación cruzada: 92,7 % (51/55) con 4 falsos positivos; 100 % en el conjunto externo.
El recall de las reglas sobre el corpus es optimista: los patrones nuevos se escribieron viendo
los errores. Si el clasificador dice «crisis» pero la regla no lo acepta, se usa la siguiente
intención o una aclaración que invita a contar más y recuerda la Línea de la Vida.

**Conversación.** Cada intención tiene 2–3 respuestas que rotan sin repetirse. Las que terminan
con una pregunta («¿Quieres que te enseñe un ejercicio de respiración?») dejan la oferta
pendiente un turno, y la interfaz muestra «Sí, por favor» / «No, gracias». La capa deliberativa
ofrece cita tras 3 intenciones emocionales seguidas (prioritaria) y la respiración solo si la
respuesta no trae ya su propia pregunta: dos preguntas juntas vuelven ambiguo un «sí». Tras 2
aclaraciones da la lista de temas y, después de una crisis, antepone los recursos de ayuda.
Parámetros y textos: `modelo/conocimiento/reglas.json` (versión 2.2.0).

**Limitaciones conocidas** (con prueba marcada `xfail`): «qué lástima» activa el protocolo de
crisis porque el clasificador asocia «lástima» con «me estoy lastimando». El corpus sigue siendo
sintético y pequeño; la mejora de fondo es reentrenar con mensajes reales y consentidos.

## API (`/api/v1`)

| Ruta | Clave | Descripción |
|---|---|---|
| `GET /salud` | — | Estado, modelos cargados, umbrales y versiones. 503 si falta el modelo de texto |
| `POST /intencion` | `X-API-Key` | `{texto}` → intención, confianza, crisis |
| `POST /imagen` | `X-API-Key` | multipart `imagen` → expresión, confianza, supera_umbral |
| `POST /chat` | `X-API-Key` | Turno completo. JSON, o multipart si hay imagen (`texto`, `estado`, `consentimiento`, `imagen`) |
| `GET /metricas` | `X-Admin-Key` | Contadores, tasas de crisis y aclaración, percentiles de latencia |

Errores: `{"error": {"codigo", "mensaje", "id_solicitud"}}` con 400, 401, 413, 415, 429, 500, 503.

- **Degradación segura**: sin modelo visual (o si tarda > 5 s) el turno sigue solo con texto; sin
  modelo de texto, `/chat` sigue detectando crisis por reglas y responde con recursos de ayuda.
- **Límite de frecuencia**: la API recibe todo desde el servidor de Streamlit (la misma IP), así que
  limita por la cabecera `X-Doki-Sesion` (identificador aleatorio de la pestaña): 20/min por sesión,
  más 120/min globales. Configurable con `DOKI_LIMITE_SESION` y `DOKI_LIMITE_GLOBAL`.
- **Registros**: `logs/eventos.jsonl`, una línea JSON por solicitud, rotación de 1 MB × 5. Solo
  metadatos (lista blanca de campos): nunca texto, imágenes, respuestas, estado ni IP.

## Interfaz

Si la API no responde y el mensaje parece de crisis (`app/crisis_local.py`), la interfaz muestra
el protocolo de ayuda por sí misma antes del aviso de error.

## Entrenar y evaluar

```bash
python -m modelo.entrenamiento.entrenar_intenciones
python -m modelo.entrenamiento.entrenar_vision
python -m modelo.entrenamiento.evaluar_vision
```
