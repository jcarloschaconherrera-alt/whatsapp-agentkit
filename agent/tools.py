# agent/tools.py — Herramientas del agente Leo Guadarrama
# Generado por AgentKit

import os
import yaml
import logging
from datetime import datetime

logger = logging.getLogger("agentkit")


def cargar_info_negocio() -> dict:
    """Carga la información del negocio desde business.yaml."""
    try:
        with open("config/business.yaml", "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        logger.error("config/business.yaml no encontrado")
        return {}


def obtener_horario() -> dict:
    """Retorna el horario de atención y si está abierto ahora."""
    info = cargar_info_negocio()
    horario = info.get("negocio", {}).get("horario", "Lunes a Sábado de 9:00 AM a 6:00 PM")

    ahora = datetime.now()
    dia_semana = ahora.weekday()   # 0=Lunes, 6=Domingo
    hora_actual = ahora.hour

    # Lunes a Sábado (0-5), 9am a 6pm
    esta_abierto = (dia_semana <= 5) and (9 <= hora_actual < 18)

    return {
        "horario": horario,
        "esta_abierto": esta_abierto,
        "dia": ahora.strftime("%A"),
        "hora": ahora.strftime("%H:%M"),
    }


def obtener_info_paquetes() -> str:
    """Retorna la información de precios y paquetes del sistema NOA."""
    return """
    PAQUETES DISPONIBLES:

    1. SOFTWARE PACK NOA — $159 inscripción + $115 al mes
       Incluye: Academia de trading + Señales Elite + Scanner Hummingbird + Diario de Trading
       Precio regular: $259.99 | Precio especial: $159
       Bono: $35 por cada cliente que inscribas personalmente

    2. DERECHOS DE VENTA — $29 entrada + $20 al mes
       Para construir un negocio compartiendo el sistema NOA

    Para más información o inscripción, un asesor de Leo te contactará directamente.
    """


def obtener_info_sistema_noa() -> str:
    """Retorna descripción del sistema NOA con sus 3 pilares."""
    return """
    EL SISTEMA NOA tiene 3 pilares:

    1. EDUCACIÓN: Academia de trading en vivo y pregrabada.
       Cursos de Forex y Cripto desde principiante hasta avanzado.

    2. HERRAMIENTAS:
       - Señales Elite: +10 traders expertos enviando señales en tiempo real
       - LUMEN: IA que analiza criptomonedas y da ideas de trading
       - Scanner HUMMINGBIRD (principiantes) y MAITRYX (avanzado): alertas con 85% de eficacia
       - Diario de Trading automático

    3. ACOMPAÑAMIENTO: En 72 horas empiezas a operar con guías paso a paso.
    """


def registrar_lead(telefono: str, nombre: str, interes: str) -> str:
    """
    Registra un prospecto interesado para seguimiento.
    En producción, esto podría conectarse a un CRM.
    """
    logger.info(f"LEAD REGISTRADO — Tel: {telefono} | Nombre: {nombre} | Interés: {interes}")
    return f"Lead registrado: {nombre} ({telefono}) — Interés: {interes}"
