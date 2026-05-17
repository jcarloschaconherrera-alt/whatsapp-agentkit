# agent/scheduler.py — Scheduler de follow-ups para el flujo Sesión en Vivo

import os
import logging
from datetime import datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore

from agent.memory import obtener_lead
from agent.providers import obtener_proveedor

logger = logging.getLogger("agentkit")

# SQLAlchemy síncrono para el jobstore (APScheduler no usa async aquí)
_DB_URL = os.getenv("DATABASE_URL", "sqlite:///./data/agentkit.db")
_JOBSTORE_URL = _DB_URL.replace("sqlite+aiosqlite:///", "sqlite:///").replace("postgresql+asyncpg://", "postgresql://")

scheduler = AsyncIOScheduler(
    jobstores={"default": SQLAlchemyJobStore(url=_JOBSTORE_URL)}
)


async def enviar_followup_sesion(telefono: str):
    """Envía mensaje de follow-up 30 min después de la bienvenida de la sesión."""
    lead = await obtener_lead(telefono)
    if not lead or lead.etapa_reto in ("sesion_confirmada", "completado", "inactivo"):
        logger.info(f"Follow-up cancelado para {telefono} — etapa: {lead.etapa_reto if lead else 'no existe'}")
        return

    nombre = lead.nombre or "amigo"
    link = os.getenv("LINK_GRUPO_SESION", "")

    msg = (
        f"Oye {nombre}, ¿ya entraste al grupo de la sesión? 👀\n\n"
        "Solo por ahí te envío el link de la sesión y los materiales.\n\n"
        f"Por si acaso: {link}"
    )

    await obtener_proveedor().enviar_mensaje(telefono, msg)
    logger.info(f"Follow-up sesión enviado a {telefono}")


def programar_followup(telefono: str, minutos: int = 30):
    """Programa un follow-up para el lead en N minutos."""
    scheduler.add_job(
        enviar_followup_sesion,
        "date",
        run_date=datetime.now() + timedelta(minutes=minutos),
        args=[telefono],
        id=f"followup_sesion_{telefono}",
        replace_existing=True,
    )
    logger.info(f"Follow-up programado para {telefono} en {minutos} min")
