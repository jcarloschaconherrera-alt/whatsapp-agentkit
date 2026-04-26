# tests/test_local.py — Simulador de chat en terminal
# Generado por AgentKit

"""
Prueba el Asistente Leo Guadarrama sin necesitar WhatsApp.
Simula una conversación en la terminal como si fueras un cliente.
"""

import asyncio
import sys
import os

# Agregar el directorio raíz al path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.brain import generar_respuesta
from agent.memory import inicializar_db, guardar_mensaje, obtener_historial, limpiar_historial

TELEFONO_TEST = "test-local-001"


async def main():
    """Loop principal del chat de prueba."""
    await inicializar_db()

    print()
    print("=" * 60)
    print("   Asistente Leo Guadarrama — Test Local")
    print("=" * 60)
    print()
    print("  Escribe mensajes como si fueras un prospecto o alumno.")
    print("  Comandos especiales:")
    print("    'limpiar'  — borra el historial de esta sesión")
    print("    'salir'    — termina el test")
    print()
    print("-" * 60)
    print()

    while True:
        try:
            mensaje = input("Tú: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\nTest finalizado.")
            break

        if not mensaje:
            continue

        if mensaje.lower() == "salir":
            print("\nTest finalizado.")
            break

        if mensaje.lower() == "limpiar":
            await limpiar_historial(TELEFONO_TEST)
            print("[Historial borrado — nueva conversación]\n")
            continue

        # Obtener historial ANTES de guardar el mensaje actual
        historial = await obtener_historial(TELEFONO_TEST)

        # Generar respuesta del Asistente Leo Guadarrama
        print("\nAsistente Leo Guadarrama: ", end="", flush=True)
        respuesta = await generar_respuesta(mensaje, historial)
        print(respuesta)
        print()

        # Guardar el intercambio
        await guardar_mensaje(TELEFONO_TEST, "user", mensaje)
        await guardar_mensaje(TELEFONO_TEST, "assistant", respuesta)


if __name__ == "__main__":
    asyncio.run(main())
