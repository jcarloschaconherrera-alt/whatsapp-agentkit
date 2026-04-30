# agent/tools.py — Herramientas del agente Leo Guadarrama Trading Academy
# Generado por AgentKit

"""
Herramientas específicas del negocio.
Casos de uso: FAQ sobre NOA, calificación de leads y soporte post-venta.
"""

import os
import yaml
import logging

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
    """Retorna el horario de atención del negocio."""
    info = cargar_info_negocio()
    return {
        "horario": info.get("negocio", {}).get("horario", "Lunes a Sábado 9am a 6pm"),
        "esta_abierto": True,
    }


def buscar_en_knowledge(consulta: str) -> str:
    """
    Busca información relevante en los archivos de /knowledge.
    Retorna el contenido más relevante encontrado.
    """
    resultados = []
    knowledge_dir = "knowledge"

    if not os.path.exists(knowledge_dir):
        return "No hay archivos de conocimiento disponibles."

    for archivo in os.listdir(knowledge_dir):
        ruta = os.path.join(knowledge_dir, archivo)
        if archivo.startswith(".") or not os.path.isfile(ruta):
            continue
        try:
            with open(ruta, "r", encoding="utf-8") as f:
                contenido = f.read()
                if consulta.lower() in contenido.lower():
                    resultados.append(f"[{archivo}]: {contenido[:500]}")
        except (UnicodeDecodeError, IOError):
            continue

    if resultados:
        return "\n---\n".join(resultados)
    return "No encontré información específica sobre eso en mis archivos."


def registrar_lead(telefono: str, nombre: str = "", interes: str = "") -> str:
    """
    Registra un prospecto interesado para seguimiento.
    Retorna un mensaje de confirmación.
    """
    logger.info(f"Nuevo lead registrado — Tel: {telefono}, Nombre: {nombre}, Interés: {interes}")
    return f"Lead registrado: {nombre or telefono} interesado en {interes or 'el sistema NOA'}"


def calificar_lead(perfil: str) -> str:
    """
    Califica un lead según su perfil.

    Perfiles:
    - PERSONA_A: Quiere ser embajador Y hacer trading
    - PERSONA_B: Solo quiere aprender trading
    - PERSONA_C: Tiene dudas puntuales
    """
    perfiles = {
        "PERSONA_A": "Prospecto de alto valor — ofrecer Software Gold Pack + Derechos de Venta",
        "PERSONA_B": "Prospecto educativo — ofrecer Software Pack o Paquete 3 Meses",
        "PERSONA_C": "Prospecto informativo — resolver dudas y abrir puerta a siguiente paso",
    }
    return perfiles.get(perfil.upper(), "Perfil no identificado — hacer más preguntas para calificar")


def obtener_paquete_recomendado(perfil: str, presupuesto: str = "") -> dict:
    """
    Retorna el paquete recomendado según el perfil del prospecto.
    """
    paquetes = {
        "principiante": {
            "nombre": "Software Pack",
            "inscripcion": "$159",
            "mensualidad": "$115/mes",
            "descripcion": "Ideal para comenzar: Academia + Señales + Scanner Hummingbird + Diario"
        },
        "intermedio": {
            "nombre": "Software Pro Pack",
            "inscripcion": "$200",
            "mensualidad": "$159/mes",
            "descripcion": "Todo el Pack base + Índices XTRA + App Desliza y Gana"
        },
        "avanzado": {
            "nombre": "Software Gold Pack",
            "inscripcion": "$299",
            "mensualidad": "$245/mes",
            "descripcion": "Todo lo anterior + Scanner MAITRYX avanzado"
        },
        "3meses": {
            "nombre": "Paquete 3 Meses",
            "precio": "$365 (50% OFF)",
            "descripcion": "Señales VIP + Lumen Cripto + Hummingbird + Trading Journal + Acompañamiento"
        }
    }

    nivel = "principiante"
    if "avanzado" in perfil.lower() or "gold" in perfil.lower():
        nivel = "avanzado"
    elif "intermedio" in perfil.lower() or "pro" in perfil.lower():
        nivel = "intermedio"
    elif "3 mes" in perfil.lower() or "tres mes" in perfil.lower():
        nivel = "3meses"

    return paquetes.get(nivel, paquetes["principiante"])
