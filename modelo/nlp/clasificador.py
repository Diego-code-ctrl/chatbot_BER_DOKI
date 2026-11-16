"""Envoltorio del clasificador de intenciones entrenado, compartido por el agente y la API"""
from pathlib import Path

import joblib

from modelo.config import MODELOS
from modelo.nlp import intenciones


class ClasificadorTexto:
    def __init__(self, pipeline, umbral: float):
        self.pipeline = pipeline
        self.umbral = umbral

    @classmethod
    def cargar(cls, ruta: Path | None = None) -> 'ClasificadorTexto':
        artefacto = joblib.load(ruta or MODELOS / 'intenciones.joblib')
        return cls(artefacto['modelo'], artefacto['umbral'])

    def terminos_conocidos(self, texto: str) -> int:
        """
        Cuántos términos del mensaje están en el vocabulario TF-IDF. Con cero, el vector es nulo y el
        SVM cae en la clase con mayor sesgo (hoy, crisis): ese resultado no significa nada.
        """
        vectorizador = self.pipeline.named_steps.get('vec')
        if vectorizador is None:
            return 1
        # Con la representación mixta cuentan solo las palabras: los n-gramas de caracteres
        # casi nunca quedan vacíos, ni siquiera con texto sin sentido
        if hasattr(vectorizador, 'transformer_list'):
            vectorizador = dict(vectorizador.transformer_list)['palabras']
        return vectorizador.transform([texto]).nnz

    def alternativa(self, texto: str, excluir: str = 'crisis') -> tuple[str, float]:
        """Intención más probable sin contar `excluir`: se usa cuando la regla de crisis rechaza esa etiqueta"""
        probabilidades = self.pipeline.predict_proba([texto])[0]
        orden = [i for i in probabilidades.argsort()[::-1] if self.pipeline.classes_[i] != excluir]
        return str(self.pipeline.classes_[orden[0]]), float(probabilidades[orden[0]])

    def clasificar(self, texto: str) -> tuple[str, float, int]:
        """Intención más probable, su probabilidad y el número de términos conocidos del mensaje"""
        intencion, confianza = intenciones.predecir_con_confianza(self.pipeline, texto)
        return intencion, confianza, self.terminos_conocidos(texto)
