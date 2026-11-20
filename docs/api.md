# Referencia de la API (`/api/v1`)

Cuerpos en JSON; la imagen va en `multipart/form-data`. La API no guarda estado entre solicitudes.
Todas las rutas salvo `/salud` y `/metricas` exigen la cabecera `X-API-Key`. La interfaz envía además
`X-Doki-Sesion` (identificador aleatorio de la pestaña, 16–64 caracteres hexadecimales) para el límite de frecuencia.

## Rutas

| Ruta | Clave | Entrada | Salida |
|---|---|---|---|
| `GET /salud` | — | — | `estado` (`listo`/`no_listo`), `modelos`, `umbrales`, `version_modelos`. 503 si falta el modelo de texto |
| `POST /intencion` | `X-API-Key` | `{"texto"}` | `intencion`, `confianza`, `crisis`, `bajo_umbral` |
| `POST /imagen` | `X-API-Key` | multipart `imagen` (JPEG/PNG ≤ 5 MB) | `expresion`, `confianza`, `supera_umbral` |
| `POST /chat` | `X-API-Key` | JSON `{"texto", "estado", "consentimiento"}` o multipart con `texto`, `estado` (JSON en texto), `consentimiento` (`true`/`false`) e `imagen` | Turno completo (abajo) |
| `GET /metricas` | `X-Admin-Key` | — | Solicitudes y errores por ruta, acciones, intenciones, activaciones (crisis, aclaración, imagen), tasas de crisis y aclaración en `/chat` y latencia p50/p95/p99 por ruta |

Todas las respuestas llevan `X-Request-Id`, que coincide con `id_solicitud`.

## Respuesta de `/chat`

```json
{
  "id_solicitud": "a1b2c3d4e5f6",
  "respuesta": [
    {"tipo": "texto", "contenido": "…respuesta de la intención…"},
    {"tipo": "imagen", "contenido": "Me parece ver una expresión triste o cansada, aunque puedo equivocarme…"}
  ],
  "intencion": "estres_academico",
  "confianza_texto": 0.86,
  "expresion": "tristeza",
  "confianza_visual": 0.71,
  "accion": "responder",
  "estado": {"intenciones": ["estres_academico"], "aclaraciones": 0, "ofertas": [], "oferta_pendiente": "organizacion_tiempo", "vistas": {"estres_academico": 1}},
  "version_modelos": {"conocimiento": "2.2.0", "texto": "svm-tfidf@969e110d", "imagen": "efficientnet_b0@fb18d9ad"}
}
```

**Tipos de segmento:** `texto`, `crisis` (protocolo de ayuda), `imagen` (frase sobre la expresión o aviso), `oferta` (cita o respiración), `recursos` (ayuda disponible tras una crisis).

**Acciones:** `responder`, `aclaracion`, `pausa`, `crisis`, `pedir_imagen`, `despedida`, `rechazo_oferta`, `error_modelo` (sin modelo de texto: recursos de ayuda).

## Errores

Formato único: `{"error": {"codigo": "…", "mensaje": "…", "id_solicitud": "…"}}`.

| HTTP | Código | Cuándo |
|---|---|---|
| 400 | `TEXTO_INVALIDO`, `TEXTO_MUY_LARGO`, `ESTADO_INVALIDO`, `IMAGEN_AUSENTE` | Texto vacío, más de 500 caracteres, estado que no es un objeto JSON, falta la imagen en `/imagen` |
| 401 | `NO_AUTORIZADO` | Falta la clave o es incorrecta (el mensaje no explica el motivo) |
| 413 | `IMAGEN_MUY_GRANDE` | Imagen de más de 5 MB |
| 415 | `FORMATO_NO_ADMITIDO` | No es JPEG ni PNG, o el archivo no es una imagen válida |
| 429 | `DEMASIADAS_SOLICITUDES` | Más de 20 solicitudes por minuto en una sesión o 120 por minuto en total |
| 500 | `ERROR_INTERNO` | Fallo no previsto (se registra el tipo de excepción, nunca el contenido) |
| 404, 405 | `RUTA_NO_ENCONTRADA`, `METODO_NO_PERMITIDO` | Ruta o método inexistente |
| 503 | `MODELO_NO_CARGADO`, `MODELO_NO_DISPONIBLE` | Falta el modelo requerido o falló el análisis de la imagen |

## Ejemplos

```bash
curl https://<túnel>/api/v1/salud
curl -X POST https://<túnel>/api/v1/chat -H "X-API-Key: $DOKI_API_KEY" -H "Content-Type: application/json" \
     -d '{"texto": "estoy muy estresado por los exámenes", "estado": {}}'
curl -X POST https://<túnel>/api/v1/chat -H "X-API-Key: $DOKI_API_KEY" \
     -F texto="así me siento hoy" -F estado='{}' -F consentimiento=true -F imagen=@foto.jpg
curl https://<túnel>/api/v1/metricas -H "X-Admin-Key: $DOKI_ADMIN_KEY"
```

## Variables de entorno

| Variable | Predeterminado | Uso |
|---|---|---|
| `DOKI_API_KEY` | — (obligatoria) | Clave que la interfaz envía en `X-API-Key` |
| `DOKI_ADMIN_KEY` | — | Clave de `/metricas` |
| `DOKI_API_HOST`, `DOKI_API_PUERTO`, `DOKI_API_HILOS` | `127.0.0.1`, `8000`, `4` | Servidor Waitress |
| `DOKI_LIMITE_SESION`, `DOKI_LIMITE_GLOBAL` | `20 per minute`, `120 per minute` | Límites de frecuencia |
| `DOKI_MAX_CARACTERES`, `DOKI_MAX_BYTES_IMAGEN` | `500`, `5242880` | Límites de entrada |
| `DOKI_DIR_REGISTROS` | `logs/` | Carpeta de `eventos.jsonl` |
