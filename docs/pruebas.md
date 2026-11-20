# Pruebas

## Pruebas automáticas

```bash
pytest                                  # 58 pruebas + 1 limitación conocida (xfail)
python -m scripts.ejecutar_casos        # casos de la sección 9 con lo observado → resultados/casos_prueba.csv
python -m scripts.medir_desempeno       # latencia, memoria y carga → resultados/desempeno_local.{csv,json}
```

| Archivo | Cubre |
|---|---|
| `tests/test_api.py` | A1–A9, contrato de `/chat`, formato de error, `/metricas` con clave |
| `tests/test_agente.py` | G1–G10, ofertas «sí»/«no», rotación de respuestas, crisis por palabra exacta, faltas de ortografía, saneamiento del estado |
| `tests/test_degradacion.py` | E2, E3 y que los registros nunca contengan el texto del mensaje |
| `tests/test_interfaz.py` | E1, E4 y la detección local de crisis |

Limitación conocida (`xfail`): «qué lástima que no fui» activa el protocolo de crisis.

## Casos de la sección 9 (ejecución automática)

Ejecutados en local con los modelos reales (`svm-tfidf@969e110d`, `efficientnet_b0@fb18d9ad`,
conocimiento 2.2.0). En G3, G4 y G7 la expresión se fija con un clasificador simulado, porque lo
que se prueba es la política del agente y el repositorio no incluye fotos de rostros. En A5 la imagen
es un recorte de la lámina de muestras de FER-2013.

**Resultado: 23 de 23 casos cumplen.**

### 9.1 API

| Caso | | Resultado obtenido | Cumple |
|---|---|---|---|
| A1 | Salud | 200; estado=listo; versiones={'conocimiento': '2.2.0', 'imagen': 'efficientnet_b0@fb18d9ad', 'texto': 'svm-tfidf@969e110d'} | Sí |
| A2 | Texto válido | 200; intención=estres_academico; confianza=0.86 | Sí |
| A3 | Texto vacío | 400; código=TEXTO_INVALIDO | Sí |
| A4 | Texto demasiado largo | 400; código=TEXTO_MUY_LARGO | Sí |
| A5 | Imagen válida | 200; expresión=tristeza; confianza=0.26; supera_umbral=False | Sí |
| A6 | Imagen demasiado grande | 413; código=IMAGEN_MUY_GRANDE | Sí |
| A7 | Formato no admitido | texto disfrazado: 415; GIF: 415; código=FORMATO_NO_ADMITIDO | Sí |
| A8 | Sin clave | 401; código=NO_AUTORIZADO; mensaje=«Servicio no disponible.» | Sí |
| A9 | Límite de frecuencia | 22 solicitudes de una sesión: 200 hasta la 20.ª, 429 desde la 21.ª (límite 20/min); otra sesión al mismo tiempo: 200 | Sí |

### 9.2 Agente

| Caso | | Resultado obtenido | Cumple |
|---|---|---|---|
| G1 | Saludo | acción=responder; intención=saludo (0.88) | Sí |
| G2 | Crisis explícita | acción=crisis; segmentos=['crisis']; incluye 911 y línea de contacto: True | Sí |
| G3 | Crisis con la imagen contraria | acción=crisis; modelo visual llamado 0 veces; expresión en la respuesta=None | Sí |
| G4 | Imagen sin crisis | acción=responder; expresión=tristeza (0.9); frase=«Me parece ver una expresión triste o cansada, aunque puedo equivocarme. ¿Quieres contarme cómo te sientes?» | Sí |
| G5 | Imagen sin consentimiento | acción=responder; modelo visual llamado 0 veces; expresión=None | Sí |
| G6 | Texto ambiguo | acción=aclaracion; confianza=0.1118 | Sí |
| G7 | Contradicción texto-imagen | intención=estres_academico; expresión=alegría; frase=«En tu imagen me parece ver una expresión de alegría, pero lo que me escribes cuenta más que una foto, así que sigo con lo que me cuentas.» | Sí |
| G8 | Regla de pausa | acción=pausa | Sí |
| G9 | Memoria de sesión | 4 turnos: 4 respuestas distintas; ofertas de cita en la conversación: 1; memoria=['estres_academico', 'ansiedad_examenes', 'estres_academico', 'estres_academico'] | Sí |
| G10 | Fuera de dominio | «¿quién ganó el partido?» → responder/otro_tema; «recomiéndame una película» → responder/otro_tema | Sí |

### 9.3 Errores y degradación

| Caso | | Resultado obtenido | Cumple |
|---|---|---|---|
| E1 | Apagar la API | aviso «no está disponible»: True; botón Reintentar: True; banner presente: True | Sí |
| E2 | Sin modelo visual | acción=responder; segmentos=['texto', 'imagen']; aviso=«No pude analizar la imagen en este momento, así que continúo solo con lo que me escribes.» | Sí |
| E3 | Sin modelo de texto | crisis por reglas: crisis; mensaje común: error_modelo con Línea de la Vida: True; /salud: 503 | Sí |
| E4 | Clave incorrecta en la interfaz | aviso «no está disponible»: True; muestra 401 o código técnico: False | Sí |

E5 (cerrar y reabrir el túnel) y U1–U6 (interfaz y usabilidad) se ejecutan a mano sobre la
aplicación desplegada, desde un dispositivo distinto al de desarrollo.

## Desempeño en local (sección 10.2)

Equipo: Darwin arm64, 8 núcleos, Python 3.14.6. API con Waitress (4 hilos).
Las latencias son de la API (turno completo de `/chat`), sin red: no incluyen el túnel ni Streamlit Cloud.

| Medición | Condición | Resultado |
|---|---|---|
| Latencia de texto en la API | Solo texto, en local, 100 turnos | Mediana 4.4 ms; p95 4.9 ms |
| Latencia de imagen en la API | Texto e imagen, en local, 40 turnos | Mediana 118.1 ms; p95 126.4 ms |
| Primera solicitud tras iniciar la API | Con la carga de modelos | API lista en 4.54 s; primer turno de texto 52.0 ms; primer turno con imagen 161.7 ms |
| Memoria de la API con los modelos cargados | Equipo local | ≈ 549 MB (sin cambio tras usar la visión y la carga) |
| Varias solicitudes simultáneas | 8 sesiones, 200 turnos de texto | 200/200 correctos; 257.7 turnos/s; mediana 30.7 ms; p95 34.8 ms |
| Latencia total vista por el estudiante | Con túnel y Streamlit | Pendiente: se mide con la aplicación desplegada |

En la prueba de carga los límites de frecuencia se elevaron para medir la capacidad del equipo; con
los límites normales, a partir de 120 turnos por minuto en total la API responde 429.
