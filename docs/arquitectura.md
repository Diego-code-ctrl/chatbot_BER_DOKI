# Arquitectura

## Componentes

```
Navegador ──► Streamlit Community Cloud (app/) ──HTTPS──► Túnel de Cloudflare ──► API Flask/Waitress (api/) ──► Agente (modelo/)
               interfaz sin modelos                                               valida, autentica,          reactiva → visión → deliberativa
                                                                                  limita, registra            + base de conocimiento
```

| Carpeta | Responsabilidad | No hace |
|---|---|---|
| `app/` | Captura el mensaje y la imagen, pide el consentimiento, guarda el historial en la sesión del navegador y muestra la respuesta | No carga modelos ni decide el contenido de la respuesta |
| `api/` | Valida entrada, autentica con `X-API-Key`, limita la frecuencia, da errores uniformes, registra metadatos y expone métricas | No interpreta texto ni imágenes |
| `modelo/agente/` | Decide la acción de cada turno con dos capas | No guarda nada entre solicitudes: el estado viaja con cada turno |
| `modelo/nlp/` | Preprocesamiento, clasificador de intenciones (SVM + TF-IDF de palabras y caracteres) y reglas de crisis | — |
| `modelo/vision/` | EfficientNet-B0 sobre FER-2013: dataset, arquitectura, inferencia y evaluación | — |
| `modelo/conocimiento/` | `reglas.json` versionado: respuestas, textos, palabras clave y parámetros del agente | — |
| `modelo/entrenamiento/` | Scripts de entrenamiento, evaluación y calibración | — |

## Flujo de un turno

1. La interfaz envía `texto`, el `estado` devuelto en el turno anterior, la imagen (si hay) y el consentimiento.
2. La API valida longitud, formato y tamaño. Sin consentimiento la imagen ni siquiera se decodifica.
3. **Percepción:** intención y confianza del clasificador, términos conocidos, reglas de crisis, pausa, respuesta corta («sí», «no»).
4. **Capa reactiva** (en orden; la primera que se activa decide):

| Prioridad | Regla | Efecto |
|---|---|---|
| 1 | Crisis: reglas por palabra exacta o frase, **o** clasificador con confianza ≥ 0,30, ≥ 2 términos conocidos y sin ser pausa ni respuesta corta | Protocolo de crisis; la imagen se ignora; el turno termina |
| — | Respuesta a una oferta pendiente | «Sí» cumple la oferta; «no» la descarta con respeto (`rechazo_oferta`) |
| 2 | Pausa (el mensaje entero es una duda corta) | Respuesta paciente |
| 3 | Consentimiento | Sin imagen o sin permiso, el modelo visual no se ejecuta |
| 4 | Baja confianza (< 0,25), sin vocabulario conocido con confianza < 0,5, o «crisis» rechazada por la regla 1 | Aclaración (si hubo señal de crisis, aclaración que recuerda la Línea de la Vida) |

5. **Visión** (si hay permiso): expresión aparente con umbral 0,55 y tiempo máximo de 5 s. Es un matiz, nunca una decisión: si contradice al texto, prevalece el texto y se explica.
6. **Capa deliberativa:** ofrece cita tras 3 intenciones emocionales seguidas (prioritaria), respiración solo si la respuesta no trae ya su propia pregunta, lista de temas tras 2 aclaraciones y recursos de ayuda en cada turno posterior a una crisis.
7. La API devuelve la respuesta en segmentos, la intención, la acción, las confianzas, el estado nuevo y las versiones de los modelos.

## Decisiones de diseño

- **Agente híbrido por capas.** La seguridad (crisis) vive en la capa reactiva y se evalúa siempre primero; ninguna meta deliberativa puede desplazarla.
- **API sin estado.** La memoria de sesión viaja con cada solicitud y se sanea al llegar (`EstadoSesion.desde_dict`). Reiniciar la API no pierde conversaciones y el servidor no guarda nada de los estudiantes.
- **Dos procesos.** La interfaz corre en Streamlit Community Cloud con recursos acotados; los modelos (PyTorch) corren en el equipo local detrás del túnel.
- **Sin reintentos automáticos.** Un reintento silencioso podría duplicar un turno de crisis; se ofrece un botón «Reintentar».
- **Degradación segura.** Sin modelo visual el turno sigue con texto; sin modelo de texto las reglas de crisis siguen activas y se responden recursos de ayuda; si la API no responde, la interfaz detecta crisis con una expresión regular local (`app/crisis_local.py`) y muestra el protocolo.
- **Conocimiento separado del código.** Textos, umbrales y palabras clave están en `reglas.json` (versión 2.2.0), que se puede revisar con un profesional sin tocar Python.
