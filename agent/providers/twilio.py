# agent/providers/twilio.py — Adaptador para Twilio WhatsApp
# Generado por AgentKit

import os
import logging
import base64
import httpx
from fastapi import Request
from agent.providers.base import ProveedorWhatsApp, MensajeEntrante

logger = logging.getLogger("agentkit")


class ProveedorTwilio(ProveedorWhatsApp):
    """Proveedor de WhatsApp usando Twilio."""

    def __init__(self):
        self.account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        self.auth_token = os.getenv("TWILIO_AUTH_TOKEN")
        self.phone_number = os.getenv("TWILIO_PHONE_NUMBER")

    async def parsear_webhook(self, request: Request) -> list[MensajeEntrante]:
        """
        Parsea el payload form-encoded de Twilio.
        Twilio envía los mensajes como application/x-www-form-urlencoded.
        """
        try:
            form = await request.form()
        except Exception:
            # Si no es form, intentar JSON (fallback)
            return []

        texto = form.get("Body", "")
        telefono_raw = form.get("From", "")
        # Twilio prefija con "whatsapp:" — lo removemos para tener solo el número
        telefono = telefono_raw.replace("whatsapp:", "")
        mensaje_id = form.get("MessageSid", "")

        if not texto:
            return []

        return [MensajeEntrante(
            telefono=telefono,
            texto=texto,
            mensaje_id=mensaje_id,
            es_propio=False,  # Twilio solo envía mensajes entrantes al webhook
        )]

    async def enviar_mensaje(self, telefono: str, mensaje: str) -> bool:
        """
        Envía mensaje via Twilio WhatsApp API.
        Twilio requiere el prefijo 'whatsapp:' en los números.
        """
        if not all([self.account_sid, self.auth_token, self.phone_number]):
            logger.warning("Variables de Twilio no configuradas — mensaje no enviado")
            return False

        url = f"https://api.twilio.com/2010-04-01/Accounts/{self.account_sid}/Messages.json"
        credentials = base64.b64encode(
            f"{self.account_sid}:{self.auth_token}".encode()
        ).decode()
        headers = {"Authorization": f"Basic {credentials}"}

        # Asegurar formato correcto de números
        from_number = self.phone_number
        if not from_number.startswith("whatsapp:"):
            from_number = f"whatsapp:{from_number}"

        to_number = telefono
        if not to_number.startswith("whatsapp:"):
            to_number = f"whatsapp:{to_number}"

        data = {
            "From": from_number,
            "To": to_number,
            "Body": mensaje,
        }

        async with httpx.AsyncClient() as client:
            r = await client.post(url, data=data, headers=headers)
            if r.status_code not in (200, 201):
                logger.error(f"Error Twilio: {r.status_code} — {r.text}")
                return False
            logger.info(f"Mensaje enviado a {telefono} via Twilio")
            return True
