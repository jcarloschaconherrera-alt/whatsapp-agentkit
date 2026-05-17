# agent/memory.py — Memoria de conversaciones y perfiles de leads con SQLite
# Generado por AgentKit — Extendido para Recolección de Datos Reto 200→400

"""
Sistema de memoria del agente. Guarda:
- Historial de conversaciones por número de teléfono (tabla mensajes)
- Perfil estructurado de cada lead (tabla leads)
"""

import os
from datetime import datetime
from typing import Optional
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Text, DateTime, select, Integer, update
from dotenv import load_dotenv

load_dotenv()

# Configuración de base de datos
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./agentkit.db")

# Si es PostgreSQL en producción, ajustar el esquema de URL
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

engine = create_async_engine(DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class Mensaje(Base):
    """Modelo de mensaje en la base de datos."""
    __tablename__ = "mensajes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telefono: Mapped[str] = mapped_column(String(50), index=True)
    role: Mapped[str] = mapped_column(String(20))  # "user" o "assistant"
    content: Mapped[str] = mapped_column(Text)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# ---------------------------------------------------------------------------
# Modelo Lead — perfil estructurado de cada prospecto
# ---------------------------------------------------------------------------

class Lead(Base):
    """
    Perfil estructurado de un prospecto.
    Se crea en el primer mensaje y se enriquece durante la conversación.

    Etapas del reto (etapa_reto):
      nuevo            → primer contacto recibido
      paso1_enviado    → agente mandó link del broker
      paso1_confirmado → usuario confirmó registro en broker
      paso2_enviado    → agente mandó instrucción de fondear $200
      paso2_confirmado → usuario confirmó fondeo
      completado       → se envió link del grupo + se notificó al equipo
      follow_up_24h    → sin respuesta 24h después del último envío
      follow_up_72h    → sin respuesta 72h (último intento)
      inactivo         → sin respuesta tras los dos follow-ups
    """
    __tablename__ = "leads"

    telefono: Mapped[str] = mapped_column(String(50), primary_key=True)
    nombre: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    cumpleanos: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # "15 de marzo" o "15/03"
    fuente: Mapped[str] = mapped_column(String(50), default="whatsapp")           # "meta_ad" | "organico" | "whatsapp"
    etapa_reto: Mapped[str] = mapped_column(String(50), default="nuevo")
    score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    clasificacion: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)  # caliente|calificado|tibio|frio
    producto_interes: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    fecha_registro: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    fecha_ultima_actividad: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    notas: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


async def inicializar_db():
    """Crea las tablas si no existen."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def guardar_mensaje(telefono: str, role: str, content: str):
    """Guarda un mensaje en el historial de conversación."""
    async with async_session() as session:
        mensaje = Mensaje(
            telefono=telefono,
            role=role,
            content=content,
            timestamp=datetime.utcnow()
        )
        session.add(mensaje)
        await session.commit()


async def obtener_historial(telefono: str, limite: int = 20) -> list[dict]:
    """
    Recupera los últimos N mensajes de una conversación.

    Args:
        telefono: Número de teléfono del cliente
        limite: Máximo de mensajes a recuperar (default: 20)

    Returns:
        Lista de diccionarios con role y content
    """
    async with async_session() as session:
        query = (
            select(Mensaje)
            .where(Mensaje.telefono == telefono)
            .order_by(Mensaje.timestamp.desc())
            .limit(limite)
        )
        result = await session.execute(query)
        mensajes = result.scalars().all()

        # Invertir para orden cronológico (los más recientes están primero)
        mensajes.reverse()

        return [
            {"role": msg.role, "content": msg.content}
            for msg in mensajes
        ]


async def obtener_todos_contactos() -> list[dict]:
    """Retorna lista de contactos únicos con su último mensaje y conteo total."""
    async with async_session() as session:
        query = select(Mensaje).order_by(Mensaje.timestamp.asc())
        result = await session.execute(query)
        mensajes = result.scalars().all()

        contactos: dict[str, dict] = {}
        for msg in mensajes:
            tel = msg.telefono
            if tel not in contactos:
                contactos[tel] = {"telefono": tel, "total": 0, "ultimo_mensaje": "", "ultimo_timestamp": "", "ultimo_role": ""}
            contactos[tel]["total"] += 1
            contactos[tel]["ultimo_mensaje"] = msg.content
            contactos[tel]["ultimo_timestamp"] = msg.timestamp.isoformat()
            contactos[tel]["ultimo_role"] = msg.role

        return sorted(contactos.values(), key=lambda x: x["ultimo_timestamp"], reverse=True)


async def obtener_conversacion_completa(telefono: str) -> list[dict]:
    """Retorna todos los mensajes de un contacto en orden cronológico."""
    async with async_session() as session:
        query = select(Mensaje).where(Mensaje.telefono == telefono).order_by(Mensaje.timestamp.asc())
        result = await session.execute(query)
        mensajes = result.scalars().all()
        return [{"role": m.role, "content": m.content, "timestamp": m.timestamp.isoformat()} for m in mensajes]


async def limpiar_historial(telefono: str):
    """Borra todo el historial de una conversación."""
    async with async_session() as session:
        query = select(Mensaje).where(Mensaje.telefono == telefono)
        result = await session.execute(query)
        mensajes = result.scalars().all()
        for msg in mensajes:
            await session.delete(msg)
        await session.commit()


# ---------------------------------------------------------------------------
# CRUD de Leads
# ---------------------------------------------------------------------------

async def crear_lead(telefono: str, fuente: str = "whatsapp") -> Lead:
    """
    Crea un nuevo lead con etapa 'nuevo'.
    Si ya existe, no lo sobrescribe — retorna el existente.
    """
    async with async_session() as session:
        # Verificar si ya existe
        existente = await session.get(Lead, telefono)
        if existente:
            return existente

        lead = Lead(
            telefono=telefono,
            fuente=fuente,
            etapa_reto="nuevo",
            fecha_registro=datetime.utcnow(),
            fecha_ultima_actividad=datetime.utcnow(),
        )
        session.add(lead)
        await session.commit()
        await session.refresh(lead)
        return lead


async def obtener_lead(telefono: str) -> Optional[Lead]:
    """Retorna el perfil del lead o None si no existe."""
    async with async_session() as session:
        return await session.get(Lead, telefono)


async def actualizar_lead(telefono: str, **campos) -> bool:
    """
    Actualiza uno o varios campos del lead.

    Uso:
        await actualizar_lead(telefono, nombre="Juan", email="juan@mail.com")
        await actualizar_lead(telefono, etapa_reto="paso1_confirmado")

    Retorna True si el lead existía y se actualizó, False si no existía.
    """
    campos_validos = {
        "nombre", "email", "cumpleanos", "fuente", "etapa_reto",
        "score", "clasificacion", "producto_interes", "notas"
    }
    actualizar = {k: v for k, v in campos.items() if k in campos_validos}
    if not actualizar:
        return False

    actualizar["fecha_ultima_actividad"] = datetime.utcnow()

    async with async_session() as session:
        stmt = (
            update(Lead)
            .where(Lead.telefono == telefono)
            .values(**actualizar)
        )
        result = await session.execute(stmt)
        await session.commit()
        return result.rowcount > 0


async def obtener_todos_leads() -> list[dict]:
    """Retorna todos los leads para el CRM, ordenados por actividad reciente."""
    async with async_session() as session:
        query = select(Lead).order_by(Lead.fecha_ultima_actividad.desc())
        result = await session.execute(query)
        leads = result.scalars().all()
        return [
            {
                "telefono": l.telefono,
                "nombre": l.nombre,
                "email": l.email,
                "cumpleanos": l.cumpleanos,
                "fuente": l.fuente,
                "etapa_reto": l.etapa_reto,
                "score": l.score,
                "clasificacion": l.clasificacion,
                "producto_interes": l.producto_interes,
                "fecha_registro": l.fecha_registro.isoformat(),
                "fecha_ultima_actividad": l.fecha_ultima_actividad.isoformat(),
                "notas": l.notas,
            }
            for l in leads
        ]
