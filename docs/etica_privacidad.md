# Ética y privacidad

## Qué es y qué no es DOKi

Un asistente automatizado de orientación para estudiantes universitarios. Orienta y deriva; no
diagnostica, no recomienda medicamentos y no sustituye la atención psicológica. Así se dice en el
aviso inicial, que debe aceptarse antes de conversar.

## Recorrido de los datos

| Dato | Dónde pasa | Se guarda |
|---|---|---|
| Texto del mensaje | Navegador → Streamlit Cloud → túnel de Cloudflare → API local | No. Se procesa en memoria y se descarta |
| Imagen (opcional) | Mismo recorrido, solo con consentimiento | No. Sin consentimiento ni siquiera se decodifica |
| Historial y estado del agente | Sesión del navegador; el estado viaja en cada solicitud | Solo mientras la pestaña está abierta; «Borrar conversación» lo elimina |
| Registro técnico (`logs/eventos.jsonl`) | Equipo local | Sí: hora, ruta, código, latencias, intención, acción y banderas. **Nunca** texto, imágenes, respuestas, estado ni IP (lista blanca de campos, verificada por una prueba automática) |
| Identificador de sesión (`X-Doki-Sesion`) | Cabecera de cada solicitud | No se registra; es aleatorio y solo sirve para el límite de frecuencia |

Streamlit Community Cloud opera en Estados Unidos y Cloudflare es un intermediario de red: el texto
cruza servicios de terceros. El aviso de privacidad de la interfaz es un **borrador** que debe
revisarse con el área jurídica antes de un uso real.

## Salvaguardas

- **Crisis primero.** Es la regla de mayor prioridad, se activa por reglas o por el clasificador y no
  depende de la imagen. Funciona aunque falte el modelo de texto, y la interfaz tiene su propia
  detección si la API no responde.
- **Ayuda siempre visible.** Banner fijo con la Línea de la Vida (800 911 2000) y el 911 en todos los
  estados de la interfaz, incluido el error.
- **Consentimiento por imagen.** Se pide cada vez, en un cuadro aparte; cerrarlo equivale a no autorizar.
- **Lenguaje de posibilidad** para la expresión facial, y el texto prevalece si se contradicen.
- **Transparencia.** El panel «Cómo entendí tu mensaje» muestra la intención, la confianza, la acción y si se usó la imagen.
- **Sin reintentos silenciosos** que puedan duplicar un turno de crisis.
- **Errores sin detalles técnicos** para el estudiante; el 401 no explica su motivo.

## Riesgos que siguen abiertos

- El corpus es sintético y pequeño; los patrones de crisis y las respuestas nuevas no los ha revisado un profesional.
- Falsos positivos de crisis conocidos («qué lástima») y posibles falsos negativos con frases no vistas.
- FER-2013 tiene sesgos de edad, etnia e iluminación y etiquetas dudosas.
- El despliegue depende de un equipo personal y de servicios de terceros.

## Condiciones para pasar a un uso real

1. Validación de respuestas, patrones de crisis y protocolo por profesionales de psicología.
2. Aviso de privacidad definitivo revisado por el área jurídica.
3. Reentrenamiento con mensajes reales, anonimizados y obtenidos con consentimiento.
4. API alojada en infraestructura con disponibilidad garantizada y contrato de tratamiento de datos.
5. Un circuito humano de seguimiento para los casos de crisis.
