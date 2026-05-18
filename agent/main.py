# agent/main.py — Servidor FastAPI + Webhook de WhatsApp
# Generado por AgentKit

"""
Servidor principal del agente de WhatsApp.
Funciona con cualquier proveedor (Whapi, Meta, Twilio) gracias a la capa de providers.
"""

import os
import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from dotenv import load_dotenv

from fastapi.security import APIKeyHeader
from agent.brain import generar_respuesta
from agent.memory import (
    inicializar_db, guardar_mensaje, obtener_historial,
    obtener_todos_contactos, obtener_conversacion_completa,
    crear_lead, obtener_todos_leads,
)
from agent.providers import obtener_proveedor
from agent.scheduler import scheduler
from agent.tools import (
    actualizar_etapa_reto,
    construir_mensaje_grupo_reto,
    construir_mensaje_reto_inicial,
    detectar_ref_reto,
    es_trigger_reto_inicial,
    guardar_dato_lead,
)

load_dotenv()

# Configuración de logging según entorno
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
log_level = logging.DEBUG if ENVIRONMENT == "development" else logging.INFO
logging.basicConfig(level=log_level)
logger = logging.getLogger("agentkit")

# Proveedor de WhatsApp (se configura en .env con WHATSAPP_PROVIDER)
proveedor = obtener_proveedor()
PORT = int(os.getenv("PORT", 8000))
BASE_DIR = Path(__file__).resolve().parent.parent
MEDIA_DIR = BASE_DIR / "media"
VIDEO_BIENVENIDA_RETO_FILENAME = "bienvenida-reto-200-400.mp4"
VIDEO_BIENVENIDA_RETO_MARKER = "video_bienvenida_reto_enviado=true"
VIDEO_BIENVENIDA_RETO_DELAY_SECONDS = int(os.getenv("VIDEO_BIENVENIDA_RETO_DELAY_SECONDS", "8"))

# Rate limiter — clave por IP real (respeta X-Forwarded-For de proxies/Railway)
limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Inicializa la base de datos y el scheduler al arrancar el servidor."""
    await inicializar_db()
    scheduler.start()
    logger.info("Base de datos inicializada")
    logger.info("Scheduler de follow-ups iniciado")
    logger.info(f"Servidor AgentKit corriendo en puerto {PORT}")
    logger.info(f"Proveedor de WhatsApp: {proveedor.__class__.__name__}")
    yield
    scheduler.shutdown()


app = FastAPI(
    title="AgentKit — WhatsApp AI Agent",
    version="1.0.0",
    lifespan=lifespan
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

if MEDIA_DIR.exists():
    app.mount("/media", StaticFiles(directory=str(MEDIA_DIR)), name="media")

CRM_API_KEY = os.getenv("CRM_API_KEY", "")
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def valor_env_publico(nombre: str) -> str:
    """Lee una variable de entorno e ignora placeholders comunes."""
    valor = os.getenv(nombre, "").strip()
    if valor.lower() in {"", "pendiente", "pending", "todo", "none", "null"}:
        return ""
    return valor


def obtener_video_bienvenida_reto_url(request: Request) -> str:
    """Retorna la URL pública del video de bienvenida del Reto 200→400."""
    url_configurada = (
        valor_env_publico("VIDEO_BIENVENIDA_RETO_URL")
        or valor_env_publico("VIDEO_BIENVENIDA_URL")
    )
    if url_configurada:
        return url_configurada

    video_local = MEDIA_DIR / VIDEO_BIENVENIDA_RETO_FILENAME
    if not video_local.exists():
        return ""

    base_url = valor_env_publico("PUBLIC_BASE_URL").rstrip("/")
    if not base_url:
        # Usar el mismo host público que recibió el webhook (ideal si Twilio entra por Cloudflare/Tunnel).
        base_url = str(request.base_url).rstrip("/")
    return f"{base_url}/media/{VIDEO_BIENVENIDA_RETO_FILENAME}"


def anexar_marca_notas(notas: str | None, *marcas: str) -> str:
    """Agrega marcas a notas sin duplicarlas."""
    partes = [notas.strip()] if notas and notas.strip() else []
    texto_actual = "\n".join(partes)
    for marca in marcas:
        if marca and marca not in texto_actual:
            partes.append(marca)
            texto_actual = "\n".join(partes)
    return "\n".join(partes)


def es_trigger_sesion(texto: str) -> bool:
    """Detecta todas las frases que activan el flujo de sesión en vivo."""
    texto_lower = texto.lower()
    frases = [
        "confirmar mi lugar en la sesión",
        "confirmar mi lugar en la sesion",
        "confirmar lugar sesión gratuita",
        "confirmar lugar sesion gratuita",
        "quiero confirmar mi lugar",
        "sesión gratuita",
        "sesion gratuita",
        "me registré para la sesión",
        "me registré para la sesion",
        "me registre para la sesión",
        "me registre para la sesion",
    ]
    return any(frase in texto_lower for frase in frases)


async def verificar_crm_key(key: str = Depends(api_key_header)):
    if not CRM_API_KEY or key != CRM_API_KEY:
        raise HTTPException(status_code=401, detail="API key inválida")


@app.get("/")
@limiter.limit("60/minute")
async def health_check(request: Request):
    """Endpoint de salud para monitoreo."""
    return {"status": "ok", "service": "agentkit"}


@app.get("/webhook")
@limiter.limit("10/minute")
async def webhook_verificacion(request: Request):
    """Verificación GET del webhook (requerido por Meta Cloud API, no-op para otros)."""
    resultado = await proveedor.validar_webhook(request)
    if resultado is not None:
        return PlainTextResponse(str(resultado))
    return {"status": "ok"}


@app.post("/webhook")
@limiter.limit("30/minute")
async def webhook_handler(request: Request):
    """
    Recibe mensajes de WhatsApp via el proveedor configurado.
    Procesa el mensaje, genera respuesta con Claude y la envía de vuelta.
    """
    try:
        # Parsear webhook — el proveedor normaliza el formato
        mensajes = await proveedor.parsear_webhook(request)

        for msg in mensajes:
            # Ignorar mensajes propios o vacíos
            if msg.es_propio or not msg.texto:
                continue

            logger.info(f"Mensaje de {msg.telefono}: {msg.texto}")

            # Crear perfil de lead si es el primer contacto (idempotente — no duplica)
            fuente = os.getenv("FUENTE_DEFAULT", "whatsapp")
            lead = await crear_lead(msg.telefono, fuente=fuente)

            # Obtener historial ANTES de guardar el mensaje actual
            historial = await obtener_historial(msg.telefono)

            video_reto_pendiente = False
            video_reto_url = ""
            notas_reto = lead.notas or ""

            # Reto 200→400: respuesta determinística para usar el referido correcto (Leo/Josue)
            if es_trigger_reto_inicial(msg.texto):
                ref_reto = detectar_ref_reto(msg.texto)
                respuesta = construir_mensaje_reto_inicial(msg.texto)
                notas_reto = anexar_marca_notas(notas_reto, f"ref_reto={ref_reto}")
                await guardar_dato_lead(msg.telefono, "notas", notas_reto)
                await actualizar_etapa_reto(msg.telefono, "paso1_enviado")

                video_reto_url = obtener_video_bienvenida_reto_url(request)
                video_reto_pendiente = bool(
                    video_reto_url and VIDEO_BIENVENIDA_RETO_MARKER not in notas_reto
                )
            else:
                # Generar respuesta con Claude (pasa telefono para extracción silenciosa de datos)
                respuesta = await generar_respuesta(msg.texto, historial, telefono=msg.telefono)

            # Guardar mensaje del usuario Y respuesta del agente en memoria
            await guardar_mensaje(msg.telefono, "user", msg.texto)
            await guardar_mensaje(msg.telefono, "assistant", respuesta)

            # Reto 200→400: primero enviar video de bienvenida, esperar procesamiento,
            # luego invitar al grupo del reto, y después mandar los pasos de registro.
            # La pausa evita que WhatsApp muestre el texto antes del video cuando Twilio procesa el media.
            if video_reto_pendiente:
                enviado = await proveedor.enviar_media(
                    msg.telefono,
                    video_reto_url,
                    ""
                )
                if enviado:
                    notas_reto = anexar_marca_notas(notas_reto, VIDEO_BIENVENIDA_RETO_MARKER)
                    await guardar_dato_lead(msg.telefono, "notas", notas_reto)
                    await asyncio.sleep(VIDEO_BIENVENIDA_RETO_DELAY_SECONDS)

                await proveedor.enviar_mensaje(msg.telefono, construir_mensaje_grupo_reto())
                await asyncio.sleep(3)

            # Enviar respuesta por WhatsApp via el proveedor
            # Para el Reto, esta respuesta incluye Paso 1: link referido del broker + video YouTube,
            # Paso 2: fondear $200 USD, y opción de ayuda personalizada para fondeo.
            await proveedor.enviar_mensaje(msg.telefono, respuesta)

            # Detectar trigger de sesión → enviar video + programar follow-up
            if es_trigger_sesion(msg.texto):
                video_url = os.getenv("VIDEO_BIENVENIDA_URL", "")
                if video_url:
                    await proveedor.enviar_media(msg.telefono, video_url, "")
                from agent.scheduler import programar_followup
                programar_followup(msg.telefono, minutos=30)

            logger.info(f"Respuesta a {msg.telefono}: {respuesta}")

        return {"status": "ok"}

    except Exception as e:
        logger.error(f"Error en webhook: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/conversations")
@limiter.limit("30/minute")
async def listar_contactos(request: Request, _=Depends(verificar_crm_key)):
    """CRM — lista todos los contactos con su último mensaje."""
    contactos = await obtener_todos_contactos()
    return {"contactos": contactos}


@app.get("/api/conversations/{telefono:path}")
@limiter.limit("30/minute")
async def ver_conversacion(telefono: str, request: Request, _=Depends(verificar_crm_key)):
    """CRM — conversación completa de un contacto."""
    mensajes = await obtener_conversacion_completa(telefono)
    return {"telefono": telefono, "mensajes": mensajes}


# ---------------------------------------------------------------------------
# Endpoints de Leads (perfiles estructurados)
# ---------------------------------------------------------------------------

@app.get("/api/leads")
@limiter.limit("30/minute")
async def listar_leads(request: Request, _=Depends(verificar_crm_key)):
    """CRM — lista todos los leads con su perfil completo y etapa del reto."""
    leads = await obtener_todos_leads()
    return {"total": len(leads), "leads": leads}


@app.get("/api/leads/{telefono:path}")
@limiter.limit("30/minute")
async def ver_lead(telefono: str, request: Request, _=Depends(verificar_crm_key)):
    """CRM — perfil completo de un lead + conversación."""
    from agent.memory import obtener_lead
    lead = await obtener_lead(telefono)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead no encontrado")
    mensajes = await obtener_conversacion_completa(telefono)
    return {
        "perfil": {
            "telefono": lead.telefono,
            "nombre": lead.nombre,
            "email": lead.email,
            "cumpleanos": lead.cumpleanos,
            "fuente": lead.fuente,
            "etapa_reto": lead.etapa_reto,
            "score": lead.score,
            "clasificacion": lead.clasificacion,
            "producto_interes": lead.producto_interes,
            "fecha_registro": lead.fecha_registro.isoformat(),
            "fecha_ultima_actividad": lead.fecha_ultima_actividad.isoformat(),
            "notas": lead.notas,
        },
        "conversacion": mensajes,
    }


# ---------------------------------------------------------------------------
# Endpoint de registro de leads desde el website
# ---------------------------------------------------------------------------

class LeadRegister(BaseModel):
    telefono: str
    nombre: str = ""
    email: str = ""
    fuente: str = "website"


@app.post("/api/leads/register")
@limiter.limit("30/minute")
async def registrar_lead_website(
    data: LeadRegister, request: Request, _=Depends(verificar_crm_key)
):
    """Recibe un lead del website y lo crea en la base de datos."""
    await crear_lead(data.telefono, fuente=data.fuente)

    if data.nombre or data.email:
        from agent.tools import guardar_dato_lead
        if data.nombre:
            await guardar_dato_lead(data.telefono, "nombre", data.nombre)
        if data.email:
            await guardar_dato_lead(data.telefono, "email", data.email)

    logger.info(f"Lead registrado desde website — {data.telefono} | fuente: {data.fuente}")
    return {"status": "ok", "telefono": data.telefono}
