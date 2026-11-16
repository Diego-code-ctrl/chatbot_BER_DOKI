"""Interfaz de consola para probar el agente sin la API: python -m modelo.consola"""
from pathlib import Path

from modelo.agente import crear_agente


def iniciar_chatbot() -> None:
    agente, errores = crear_agente()
    if errores:
        print(f'(Modelos no cargados: {errores})')
    print('Hola, soy DOKi. Escribe tu mensaje, o «salir». Para adjuntar una imagen escribe: imagen:<ruta> <mensaje>')
    estado: dict = {}

    while True:
        texto = input('> ').strip()
        if texto.lower() == 'salir':
            break

        imagen, consentimiento = None, False
        if texto.startswith('imagen:'):
            ruta, _, texto = texto[len('imagen:'):].partition(' ')
            if Path(ruta).is_file():
                imagen = ruta
                consentimiento = input('¿Autorizas el uso de esta imagen solo para este mensaje? (sí/no) ').strip().lower() in ('si', 'sí')
            texto = texto or 'Te comparto una imagen'

        resultado = agente.turno(texto, estado, imagen, consentimiento)
        estado = resultado.estado
        for segmento in resultado.respuesta:
            print(f"[{segmento['tipo']}] {segmento['contenido']}")


if __name__ == '__main__':
    iniciar_chatbot()
