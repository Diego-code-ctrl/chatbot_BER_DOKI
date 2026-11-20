# Fichas de los modelos

## Modelo de texto: clasificador de intenciones

| | |
|---|---|
| Tarea | Clasificar el mensaje del estudiante en 15 intenciones |
| Algoritmo | SVM lineal calibrada (`CalibratedClassifierCV(LinearSVC)`, C = 1) |
| Representación | TF-IDF de palabras (raíces, uni y bigramas; 1.453 términos) unido a TF-IDF de n-gramas de caracteres 2–4 (2.648 rasgos), que tolera faltas de ortografía y letras alargadas |
| Datos | `datos/intenciones.csv`: 791 frases sintéticas en español redactadas con IA (410 en el Avance 2) |
| Intenciones | crisis, fuera_de_alcance, estres_academico, ansiedad_examenes, sueno, animo_bajo, tecnica_respiracion, organizacion_tiempo, solicitar_cita, horarios_ubicacion, compartir_imagen, ayuda_capacidades, otro_tema, saludo, despedida |
| Selección | Validación cruzada estratificada de 5 particiones sobre el 80 % de entrenamiento; prueba en el 20 % restante (159 mensajes) |
| Umbral de confianza | 0,25: debajo, el agente pide aclaración (2,5 % de la prueba queda bajo el umbral) |
| Artefacto | `modelos/intenciones.joblib` (versión `svm-tfidf@969e110d`) |

### Métricas

| Medida | Avance 2 | Actual |
|---|---|---|
| F1 macro en validación cruzada | 0,762 | 0,826 |
| Exactitud en prueba (modelo solo) | 79,3 % | 83,7 % |
| Exactitud en prueba (modelo + reglas de crisis) | — | 85,5 % |
| Aciertos del agente con 83 mensajes nunca vistos (`datos/intenciones_externo.csv`) | 78,3 % | 92,8 % |
| Aclaraciones en esos mensajes | 8,4 % | 4,8 % |
| Recall de crisis en esos mensajes / falsos positivos | 100 % / 1 | 100 % / 0 |

Las particiones de prueba no son comparables entre versiones porque el corpus cambió; la comparación justa es el conjunto externo.

**Intenciones más débiles (F1 en prueba):** otro_tema 0,62; animo_bajo 0,67; ayuda_capacidades 0,70; crisis (clasificador solo) 0,76.

### Crisis

La crisis se detecta si **las reglas** (palabras exactas como «suicidarme» o frases como «soy una carga»,
«no hay salida», «me hago cortes») **o el clasificador** la señalan. El clasificador solo cuenta con
confianza ≥ 0,30, al menos 2 términos conocidos y si el mensaje no es una duda corta ni un «sí»/«no».

| Medida | Valor |
|---|---|
| Recall en la prueba (11 mensajes): clasificador / reglas / combinado | 72,7 % / 90,9 % / 100 % |
| Recall combinado en validación cruzada (55 mensajes) | 92,7 % (51/55), 4 falsos positivos |
| Recall en el conjunto externo | 100 %, 0 falsos positivos |

**Cautelas.** Los patrones de las reglas se escribieron viendo errores del corpus, así que su recall
sobre él es optimista. Limitación conocida: «qué lástima que no fui» activa el protocolo, porque el
clasificador asocia «lástima» con «me estoy lastimando». Un falso positivo de crisis muestra recursos
de ayuda de más; un falso negativo es el error grave, y por eso el umbral se eligió para no perder recall.

## Modelo visual: expresión facial aparente

| | |
|---|---|
| Tarea | Estimar la expresión aparente en 7 clases: enojo, asco, miedo, alegría, tristeza, sorpresa, neutral |
| Arquitectura | EfficientNet-B0 preentrenada en ImageNet, ajustada (PyTorch) |
| Datos | FER-2013 (rostros 48×48 en escala de grises), con limpieza de duplicados y pesos por clase |
| Prueba | 3.276 imágenes |
| Umbral | 0,55: debajo, la imagen no se comenta (en validación se acepta el 58 % de las imágenes con 77,5 % de precisión) |
| Tiempo máximo | 5 s por inferencia; si se supera, el turno sigue solo con texto |
| Artefacto | `modelos/vision_efficientnet_b0.pt` (versión `efficientnet_b0@fb18d9ad`) |

| Medida | EfficientNet-B0 | CNN desde cero (referencia) |
|---|---|---|
| Exactitud | 62,6 % | 35,1 % |
| F1 macro | 0,566 | 0,291 |

F1 por clase: alegría 0,85; sorpresa 0,71; neutral 0,60; enojo 0,52; tristeza 0,52; miedo 0,41; asco 0,35.

**Cautelas.** La exactitud está dentro de la referencia humana del conjunto (65 ± 5 %), que tiene
etiquetas dudosas. Una expresión no equivale a una emoción: el agente usa la imagen como un matiz,
con lenguaje de posibilidad («me parece ver…, aunque puedo equivocarme»), nunca para decidir, y nunca
para activar o desactivar el protocolo de crisis. Los errores con mayor confianza correspondían sobre
todo a imágenes aparentemente mal etiquetadas, así que la confianza no garantiza el acierto.

## Reproducir

```bash
python -m modelo.entrenamiento.entrenar_intenciones   # entrena, elige por validación cruzada, calibra el umbral
python -m modelo.entrenamiento.evaluar_externo        # conjunto externo y calibración de crisis
python -m modelo.entrenamiento.entrenar_vision        # requiere la carpeta archive/ con FER-2013
python -m modelo.entrenamiento.evaluar_vision
```
