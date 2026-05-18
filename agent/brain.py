# agent/brain.py — Cerebro del agente: conexión con Claude API
# Generado por AgentKit — Extendido para Recolección de Datos Reto 200→400

"""
Lógica de IA del agente. Lee el system prompt de prompts.yaml
y genera respuestas usando la API de Anthropic Claude.

Nuevo en esta versión:
  - extraer_datos_lead(): mini-llamada a Claude que corre silenciosamente
    después de cada mensaje del usuario para detectar nombre, email y cumpleaños.
  - generar_respuesta() ahora acepta telefono para disparar la extracción.
"""

import os
import json
import yaml
import logging
from pathlib import Path
from anthropic import AsyncAnthropic
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("agentkit")

# Cliente de Anthropic
client = AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

RAG_DIR = Path("knowledge/rag")


def cargar_rag() -> str:
    """
    Carga todos los archivos .md del directorio knowledge/rag/ en orden alfabético.
    Retorna el contenido concatenado como contexto de conocimiento.
    """
    if not RAG_DIR.exists():
        logger.warning(f"Directorio RAG no encontrado: {RAG_DIR}")
        return ""

    archivos = sorted(RAG_DIR.glob("*.md"))
    if not archivos:
        logger.warning("No se encontraron archivos en el RAG")
        return ""

    secciones = []
    for archivo in archivos:
        # Saltar el índice — es metadata del RAG, no conocimiento útil para el agente
        if archivo.name == "00-indice.md":
            continue
        try:
            contenido = archivo.read_text(encoding="utf-8").strip()
            if contenido:
                secciones.append(contenido)
        except IOError as e:
            logger.error(f"Error leyendo {archivo.name}: {e}")

    rag_completo = "\n\n---\n\n".join(secciones)
    logger.info(f"RAG cargado: {len(archivos) - 1} archivos, {len(rag_completo):,} caracteres")
    return rag_completo


def cargar_config_prompts() -> dict:
    """Lee toda la configuración desde config/prompts.yaml."""
    try:
        with open("config/prompts.yaml", "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        logger.error("config/prompts.yaml no encontrado")
        return {}


def cargar_system_prompt() -> str:
    """
    Construye el system prompt completo:
    1. Base de conocimiento del RAG (knowledge/rag/*.md)
    2. Instrucciones de comportamiento y triggers (config/prompts.yaml)
    """
    rag = cargar_rag()
    config = cargar_config_prompts()
    instrucciones = config.get("system_prompt", "Eres un asistente útil. Responde en español.")

    if rag:
        return f"# BASE DE CONOCIMIENTO\n\n{rag}\n\n---\n\n# INSTRUCCIONES DE COMPORTAMIENTO\n\n{instrucciones}"
    return instrucciones


def obtener_mensaje_error() -> str:
    """Retorna el mensaje de error configurado en prompts.yaml."""
    config = cargar_config_prompts()
    return config.get(
        "error_message",
        "Lo siento, tuve un pequeño inconveniente técnico. Por favor intenta de nuevo en unos minutos."
    )


def obtener_mensaje_fallback() -> str:
    """Retorna el mensaje de fallback configurado en prompts.yaml."""
    config = cargar_config_prompts()
    return config.get(
        "fallback_message",
        "Disculpa, no entendí bien tu mensaje. ¿Podrías contarme un poco más sobre lo que necesitas?"
    )


async def extraer_datos_lead(mensaje: str, telefono: str) -> None:
    """
    Extracción silenciosa de datos del lead en cada mensaje del usuario.

    Corre una mini-llamada a Claude Haiku (modelo más barato y rápido) para detectar
    si el mensaje contiene: nombre, email o cumpleaños.
    Si detecta algo, lo guarda automáticamente en la tabla leads sin interrumpir
    el flujo de conversación principal.

    Esta función NO bloquea la respuesta principal — se ejecuta en paralelo.
    Los errores se loguean pero no se propagan.
    """
    from agent.tools import guardar_dato_lead, extraer_email_de_texto, extraer_fecha_cumpleanos
    from agent.memory import obtener_lead

    # Primero intentar extracción rápida sin IA (regex)
    email = extraer_email_de_texto(mensaje)
    if email:
        await guardar_dato_lead(telefono, "email", email)

    cumple = extraer_fecha_cumpleanos(mensaje)
    if cumple:
        await guardar_dato_lead(telefono, "cumpleanos", cumple)

    # Para el nombre usamos Claude Haiku — más rápido y barato que Sonnet
    # Solo si el lead todavía no tiene nombre guardado
    lead = await obtener_lead(telefono)
    if lead and lead.nombre:
        return  # Ya tenemos el nombre, no gastar tokens

    prompt_extraccion = (
        "Analiza el siguiente mensaje de WhatsApp y extrae el nombre propio de la persona si lo menciona.\n"
        "REGLAS:\n"
        "- Solo extrae el nombre si la persona lo dice claramente (ej: 'Me llamo Juan', 'Soy María', 'Mi nombre es Carlos')\n"
        "- Si el mensaje es un saludo corto sin nombre, responde null\n"
        "- Si hay ambigüedad, responde null\n"
        "- Responde SOLO con JSON: {\"nombre\": \"Juan\"} o {\"nombre\": null}\n\n"
        f"Mensaje: {mensaje}"
    )

    try:
        resp = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=50,
            messages=[{"role": "user", "content": prompt_extraccion}]
        )
        texto = resp.content[0].text.strip()
        datos = json.loads(texto)
        nombre = datos.get("nombre")
        if nombre and isinstance(nombre, str) and len(nombre) > 1:
            await guardar_dato_lead(telefono, "nombre", nombre.strip())
    except Exception as e:
        logger.debug(f"extraer_datos_lead: {e}")  # debug, no error — es best-effort


async def generar_respuesta(mensaje: str, historial: list[dict], telefono: str = "") -> str:
    """
    Genera una respuesta usando Claude API con prompt caching.

    El system prompt (RAG + instrucciones) se marca para cache — Anthropic lo
    mantiene en memoria 5 minutos. Lecturas subsecuentes cuestan 90% menos.

    Args:
        mensaje: El mensaje nuevo del usuario
        historial: Lista de mensajes anteriores [{"role": "user/assistant", "content": "..."}]

    Returns:
        La respuesta generada por Claude
    """
    if not mensaje or len(mensaje.strip()) < 2:
        return obtener_mensaje_fallback()

    system_prompt = cargar_system_prompt()

    if telefono:
        try:
            from agent.memory import obtener_lead
            lead = await obtener_lead(telefono)
            if lead and (
                lead.etapa_reto != "nuevo"
                or "ref_reto=" in (lead.notas or "")
                or "reto" in (lead.producto_interes or "").lower()
            ):
                system_prompt += (
                    "\n\n# CONTEXTO ACTUAL DEL LEAD\n"
                    "Este usuario ya está dentro del flujo del Reto 200 a 400. "
                    "Mantén toda la conversación enfocada en el reto, el grupo, el registro, "
                    "el fondeo de $200 USD, ayuda para fondeo y el siguiente paso después de fondear. "
                    "No uses menús genéricos A/B/C/D ni ejemplos de otros flujos. "
                    "No uses asteriscos para negritas en WhatsApp.\n"
                    f"Etapa actual: {lead.etapa_reto}\n"
                    f"Notas: {lead.notas or 'sin notas'}"
                )
        except Exception as e:
            logger.debug(f"No se pudo cargar contexto del lead: {e}")

    # Construir mensajes para la API
    mensajes = []
    for msg in historial:
        mensajes.append({
            "role": msg["role"],
            "content": msg["content"]
        })
    mensajes.append({"role": "user", "content": mensaje})

    # Extracción silenciosa de datos — corre en paralelo sin bloquear la respuesta
    import asyncio
    if telefono:
        asyncio.create_task(extraer_datos_lead(mensaje, telefono))

    try:
        response = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=[
                {
                    "type": "text",
                    "text": system_prompt,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=mensajes,
            extra_headers={"anthropic-beta": "prompt-caching-2024-07-31"},
        )

        respuesta = response.content[0].text

        # Log con detalle de cache para monitorear ahorro
        usage = response.usage
        cache_read    = getattr(usage, "cache_read_input_tokens", 0)
        cache_written = getattr(usage, "cache_creation_input_tokens", 0)
        logger.info(
            f"Respuesta generada — "
            f"in: {usage.input_tokens} | "
            f"out: {usage.output_tokens} | "
            f"cache_read: {cache_read} | "
            f"cache_write: {cache_written}"
        )
        return respuesta

    except Exception as e:
        logger.error(f"Error Claude API: {e}")
        return obtener_mensaje_error()
