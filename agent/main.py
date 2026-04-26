# agent/main.py — Servidor FastAPI + Webhook de WhatsApp
# Generado por AgentKit

import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from dotenv import load_dotenv

from agent.brain import generar_respuesta
from agent.memory import inicializar_db, guardar_mensaje, obtener_historial
from agent.providers import obtener_proveedor

load_dotenv()

# Configuración de logging
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
log_level = logging.DEBUG if ENVIRONMENT == "development" else logging.INFO
logging.basicConfig(
    level=log_level,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("agentkit")

# Proveedor de WhatsApp (Meta Cloud API según .env)
proveedor = obtener_proveedor()
PORT = int(os.getenv("PORT", 8000))


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Inicializa la base de datos al arrancar el servidor."""
    await inicializar_db()
    logger.info("Base de datos inicializada")
    logger.info(f"Agente: Asistente Leo Guadarrama")
    logger.info(f"Proveedor: {proveedor.__class__.__name__}")
    logger.info(f"Puerto: {PORT}")
    yield


app = FastAPI(
    title="Asistente Leo Guadarrama — WhatsApp AI Agent",
    version="1.0.0",
    lifespan=lifespan
)


@app.get("/")
async def health_check():
    """Endpoint de salud para Railway y monitoreo."""
    return {
        "status": "ok",
        "agente": "Asistente Leo Guadarrama",
        "version": "1.0.0"
    }


@app.get("/webhook")
async def webhook_verificacion(request: Request):
    """
    Verificación GET del webhook — requerido por Meta Cloud API.
    Meta llama a este endpoint para confirmar que el servidor existe.
    """
    resultado = await proveedor.validar_webhook(request)
    if resultado is not None:
        return resultado
    return {"status": "ok"}


@app.post("/webhook")
async def webhook_handler(request: Request):
    """
    Recibe mensajes de WhatsApp via Meta Cloud API.
    Procesa el mensaje, genera respuesta con Claude y la envía de vuelta.
    """
    try:
        # Parsear webhook — el proveedor normaliza el formato de Meta
        mensajes = await proveedor.parsear_webhook(request)

        for msg in mensajes:
            # Ignorar mensajes propios o vacíos
            if msg.es_propio or not msg.texto:
                continue

            logger.info(f"Mensaje de {msg.telefono}: {msg.texto[:50]}...")

            # Obtener historial ANTES de guardar el mensaje actual
            historial = await obtener_historial(msg.telefono)

            # Generar respuesta con Claude (Asistente Leo Guadarrama)
            respuesta = await generar_respuesta(msg.texto, historial)

            # Guardar mensaje del usuario Y respuesta del agente
            await guardar_mensaje(msg.telefono, "user", msg.texto)
            await guardar_mensaje(msg.telefono, "assistant", respuesta)

            # Enviar respuesta por WhatsApp
            exito = await proveedor.enviar_mensaje(msg.telefono, respuesta)
            if exito:
                logger.info(f"Respuesta enviada a {msg.telefono}")
            else:
                logger.error(f"Error enviando a {msg.telefono}")

        return {"status": "ok"}

    except Exception as e:
        logger.error(f"Error en webhook: {e}")
        raise HTTPException(status_code=500, detail=str(e))
