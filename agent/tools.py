# agent/tools.py — Herramientas del agente Leo Guadarrama Trading Academy
# Generado por AgentKit — Extendido para Recolección de Datos Reto 200→400

"""
Herramientas específicas del negocio.
Casos de uso: FAQ sobre NOA, calificación de leads, soporte post-venta,
y recolección estructurada de datos del flujo Reto 200→400.
"""

import os
import re
import httpx
import yaml
import logging
from agent.memory import actualizar_lead, obtener_lead

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


# ---------------------------------------------------------------------------
# Referidos del Reto 200→400
# ---------------------------------------------------------------------------

LINK_BROKER_LEO = "https://client.ebccrm.com/signup?linkCode=U6913720-e01"
LINK_BROKER_JOSUE = "https://client.myebc.co/signup?linkcode=F9090709-e01"
LINK_GRUPO_RETO_DEFAULT = "https://chat.whatsapp.com/LeXMzrrHrx78pVxqOIxjYf?mode=gi_t"
VIDEO_EXPLICATIVO_RETO_URL = "https://youtu.be/FwJ1QDCII3A?t=270"


def detectar_ref_reto(texto: str) -> str:
    """
    Detecta qué referido debe usarse para el Reto 200→400.

    Recomendado para campañas visibles al cliente:
    - Leo: usar texto natural como "Quiero el Reto 200 a 400 con Leo".
    - Josué: usar texto natural como "Quiero el Reto 200 a 400 con Maestro Josué".

    Se mantiene compatibilidad con [ref:josue] para links antiguos, pero ya no es necesario
    mostrar esa metadata al cliente.
    """
    texto_lower = texto.lower()
    if "[ref:josue]" in texto_lower:
        return "josue"

    menciones_josue = (
        "josue",
        "josué",
        "maestro josue",
        "maestro josué",
        "nuestro josue",
        "nuestro josué",
        "con josue",
        "con josué",
        "de josue",
        "de josué",
        "activacion josue",
        "activación josué",
        "campaña josue",
        "campaña josué",
    )
    if any(mencion in texto_lower for mencion in menciones_josue):
        return "josue"

    return "leo"


def obtener_link_broker_por_ref(ref: str) -> str:
    """Retorna el link de broker correspondiente al referido detectado."""
    return LINK_BROKER_JOSUE if ref.lower() == "josue" else LINK_BROKER_LEO


def es_trigger_reto_inicial(texto: str) -> bool:
    """Detecta frases iniciales del Reto 200→400, incluyendo variantes con Josue."""
    texto_lower = texto.lower()
    frases = (
        "me interesa el reto de 200 a 400",
        "me interesa el reto 200 a 400",
        "quiero el reto de 200 a 400",
        "quiero entrar al reto 200-400",
        "quiero entrar al reto de 200 a 400",
        "quiero el reto 200-400",
        "el reto de 200 a 400",
        "reto 200 400",
        "reto 200 a 400",
        "reto de 200",
        "quiero el reto",
        # Variantes limpias para campañas visibles al cliente (sin [ref:...])
        "reto con leo",
        "reto de leo",
        "activación leo",
        "activacion leo",
        "campaña leo",
        "reto con josue",
        "reto con josué",
        "reto de josue",
        "reto de josué",
        "activación josue",
        "activación josué",
        "activacion josue",
        "campaña josue",
        "campaña josué",
        "maestro josue",
        "maestro josué",
        "nuestro josue",
        "nuestro josué",
    )
    return any(frase in texto_lower for frase in frases)


def obtener_link_grupo_reto() -> str:
    """Retorna el link del grupo del Reto 200→400."""
    return os.getenv("LINK_GRUPO_RETO", "").strip() or LINK_GRUPO_RETO_DEFAULT


def construir_mensaje_grupo_reto() -> str:
    """Mensaje con llamada a acción para que el lead confirme que quiere entrar al grupo."""
    return (
        "Antes de avanzar, es importante que te unas al grupo del Reto 200 a 400.\n\n"
        "Ahí vamos a compartir avisos, materiales y acompañamiento importante para que no te pierdas ningún paso.\n\n"
        "Toca el botón: Unirme al grupo"
    )


def construir_mensaje_link_grupo_reto() -> str:
    """Envía el link del grupo después de que el usuario toca el botón."""
    link_grupo = obtener_link_grupo_reto()
    return (
        "Perfecto. Aquí tienes el link para unirte al grupo del Reto 200 a 400:\n\n"
        f"{link_grupo}\n\n"
        "Entra al grupo y después sigue con el paso a paso que te mando ahora."
    )


def es_confirmacion_unirme_grupo_reto(texto: str) -> bool:
    """Detecta cuando el usuario toca el botón o confirma que quiere entrar al grupo."""
    texto_lower = texto.lower().strip()
    frases = (
        "unirme al grupo",
        "me quiero unir al grupo",
        "quiero unirme al grupo",
        "ya entré al grupo",
        "ya entre al grupo",
        "ya estoy en el grupo",
        "entré al grupo",
        "entre al grupo",
    )
    return any(frase in texto_lower for frase in frases)


def es_ayuda_fondeo(texto: str) -> bool:
    """Detecta si el usuario pide ayuda personalizada para fondear."""
    texto_lower = texto.lower().strip()
    frases = (
        "ayuda para fondeo",
        "ayuda con fondeo",
        "ayuda para fondear",
        "ayuda con el fondeo",
        "no puedo fondear",
        "cómo fondeo",
        "como fondeo",
        "necesito ayuda para fondear",
    )
    return any(frase in texto_lower for frase in frases)


def construir_mensaje_ayuda_fondeo() -> str:
    """Respuesta corta para mantener al lead dentro del flujo del reto."""
    return (
        "Claro. Te puedo ayudar con el fondeo paso a paso.\n\n"
        "Dime en qué parte estás atorado:\n"
        "1. Registro\n"
        "2. Verificación\n"
        "3. Depósito\n"
        "4. Método de pago"
    )


def construir_mensaje_reto_inicial(texto: str) -> str:
    """Construye el mensaje inicial del Reto 200→400 con el link correcto."""
    ref = detectar_ref_reto(texto)
    link = obtener_link_broker_por_ref(ref)
    return (
        "Perfecto, ahora sí te dejo el paso a paso del Reto 200 a 400 👇\n\n"
        "Paso 1️⃣\n"
        "Registro y verificación en el broker\n"
        f"🔗 Link: {link}\n"
        f"🎥 Video explicativo desde el minuto 4:30: {VIDEO_EXPLICATIVO_RETO_URL}\n\n"
        "Paso 2️⃣\n"
        "Fondear tu cuenta con $200 USD\n\n"
        "Si necesitas ayuda personalizada para el fondeo, responde: Ayuda para fondeo\n\n"
        "Cuando ya esté fondeada tu cuenta, responde: Ya fondeé\n"
        "Ahí te doy el siguiente paso del reto."
    )


# ---------------------------------------------------------------------------
# Recolección estructurada de datos — Reto 200→400
# ---------------------------------------------------------------------------

async def guardar_dato_lead(telefono: str, campo: str, valor: str) -> bool:
    """
    Guarda un dato capturado durante la conversación en el perfil del lead.

    Campos válidos: nombre, email, cumpleanos, producto_interes, notas

    Uso desde brain.py (extracción silenciosa):
        await guardar_dato_lead(telefono, "nombre", "Juan")
        await guardar_dato_lead(telefono, "email", "juan@gmail.com")
        await guardar_dato_lead(telefono, "cumpleanos", "15 de marzo")

    Retorna True si se guardó, False si el campo no es válido.
    """
    campos_permitidos = {"nombre", "email", "cumpleanos", "producto_interes", "notas"}
    if campo not in campos_permitidos:
        logger.warning(f"guardar_dato_lead: campo '{campo}' no permitido")
        return False

    ok = await actualizar_lead(telefono, **{campo: valor})
    if ok:
        logger.info(f"Dato capturado — {telefono} | {campo}: {valor}")
    return ok


async def actualizar_etapa_reto(telefono: str, nueva_etapa: str) -> bool:
    """
    Avanza la etapa del lead en la máquina de estados del reto.

    Etapas válidas:
        nuevo → paso1_enviado → paso1_confirmado →
        paso2_enviado → paso2_confirmado → completado
        (o: follow_up_24h | follow_up_72h | inactivo)

    El agente debe llamar esta función cada vez que:
    - Envía el Paso 1 → actualizar_etapa_reto(tel, "paso1_enviado")
    - El usuario confirma Paso 1 → actualizar_etapa_reto(tel, "paso1_confirmado")
    - Envía instrucción de fondear → actualizar_etapa_reto(tel, "paso2_enviado")
    - El usuario confirma Paso 2 → actualizar_etapa_reto(tel, "paso2_confirmado")
    - Se envía el link del grupo → actualizar_etapa_reto(tel, "completado")
    """
    etapas_validas = {
        # Reto 200→400 (existentes)
        "nuevo", "grupo_pendiente", "grupo_enviado", "paso1_enviado", "paso1_confirmado",
        "paso2_enviado", "paso2_confirmado", "completado",
        "follow_up_24h", "follow_up_72h", "inactivo",
        # Sesión en vivo (existente)
        "sesion_bienvenida_enviada", "sesion_confirmada",
        # Nuevas — según botón de origen (website buttons B1-B8)
        "calificacion_consultoria",   # B1+B2 — CTA navbar/hero + EMPECEMOS
        "calificacion_sistema",       # B3 — Origin story "saber más"
        "calificacion_acceso",        # B4 — Trabaja "Quiero acceso"
        "calificacion_herramientas",  # B5 — Trabaja "Ver herramientas"
        "calificacion_capitalizar",   # B6 — Trabaja "Capitalizar"
        "calificacion_curso",         # B7 — Curso section CTA
        "escalado_equipo",            # B8 — Footer "Contacto"
    }
    if nueva_etapa not in etapas_validas:
        logger.warning(f"actualizar_etapa_reto: etapa '{nueva_etapa}' no reconocida")
        return False

    ok = await actualizar_lead(telefono, etapa_reto=nueva_etapa)
    if ok:
        logger.info(f"Etapa actualizada — {telefono} → {nueva_etapa}")
    return ok


async def notificar_equipo(telefono: str, evento: str = "completado") -> bool:
    """
    Envía una notificación al WhatsApp del equipo cuando un lead completa el reto.

    El mensaje incluye el perfil completo del lead: nombre, email, cumpleaños, etapa.
    Requiere EQUIPO_WHATSAPP_TOKEN y EQUIPO_PHONE_NUMBER_ID en .env
    (puede ser el mismo token de Meta Cloud API del agente).

    Retorna True si el mensaje se envió exitosamente.
    """
    token = os.getenv("WHATSAPP_ACCESS_TOKEN", "")
    phone_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
    numero_equipo = os.getenv("EQUIPO_WHATSAPP_NUMERO", "")  # ej: "521234567890"

    if not all([token, phone_id, numero_equipo]):
        logger.warning("notificar_equipo: faltan variables EQUIPO_WHATSAPP_NUMERO, WHATSAPP_ACCESS_TOKEN o WHATSAPP_PHONE_NUMBER_ID")
        return False

    # Obtener perfil del lead
    lead = await obtener_lead(telefono)
    nombre = lead.nombre or "Sin nombre"
    email = lead.email or "Sin email"
    cumple = lead.cumpleanos or "Sin fecha"
    etapa = lead.etapa_reto

    eventos_emoji = {
        "completado": "✅",
        "paso1_confirmado": "1️⃣",
        "paso2_confirmado": "2️⃣",
    }
    emoji = eventos_emoji.get(evento, "📋")

    mensaje = (
        f"{emoji} *Nuevo lead — Reto 200→400*\n\n"
        f"📱 Tel: {telefono}\n"
        f"👤 Nombre: {nombre}\n"
        f"📧 Email: {email}\n"
        f"🎂 Cumpleaños: {cumple}\n"
        f"📍 Etapa: {etapa}\n\n"
        f"_Evento: {evento}_"
    )

    url = f"https://graph.facebook.com/v19.0/{phone_id}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "to": numero_equipo,
        "type": "text",
        "text": {"body": mensaje}
    }
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json=payload, headers=headers, timeout=10)
            resp.raise_for_status()
            logger.info(f"Equipo notificado — evento: {evento}, lead: {telefono}")
            return True
    except Exception as e:
        logger.error(f"notificar_equipo error: {e}")
        return False


def extraer_email_de_texto(texto: str) -> str | None:
    """
    Extrae un email de un texto libre usando regex.
    Retorna el email encontrado o None.
    """
    patron = r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"
    match = re.search(patron, texto)
    return match.group(0).lower() if match else None


def extraer_fecha_cumpleanos(texto: str) -> str | None:
    """
    Extrae una fecha de cumpleaños de texto libre.
    Detecta formatos como: "15 de marzo", "15/03", "15-03", "marzo 15", "el 3 de abril".
    Retorna la fecha como string normalizado o None.
    """
    meses = {
        "enero": "01", "febrero": "02", "marzo": "03", "abril": "04",
        "mayo": "05", "junio": "06", "julio": "07", "agosto": "08",
        "septiembre": "09", "octubre": "10", "noviembre": "11", "diciembre": "12"
    }

    texto_lower = texto.lower()

    # Patrón: "15 de marzo" o "el 3 de abril"
    patron_texto = r"(?:el\s+)?(\d{1,2})\s+de\s+(" + "|".join(meses.keys()) + r")"
    match = re.search(patron_texto, texto_lower)
    if match:
        dia = match.group(1).zfill(2)
        mes = meses[match.group(2)]
        return f"{dia}/{mes}"

    # Patrón: "marzo 15"
    patron_inverso = r"(" + "|".join(meses.keys()) + r")\s+(\d{1,2})"
    match = re.search(patron_inverso, texto_lower)
    if match:
        mes = meses[match.group(1)]
        dia = match.group(2).zfill(2)
        return f"{dia}/{mes}"

    # Patrón numérico: "15/03" o "15-03"
    patron_num = r"\b(\d{1,2})[/\-](\d{1,2})\b"
    match = re.search(patron_num, texto)
    if match:
        dia = match.group(1).zfill(2)
        mes = match.group(2).zfill(2)
        if 1 <= int(dia) <= 31 and 1 <= int(mes) <= 12:
            return f"{dia}/{mes}"

    return None


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
