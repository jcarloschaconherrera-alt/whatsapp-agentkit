# Project Memory — whatsapp-agentkit

- Este proyecto se llama `whatsapp-agentkit`.
- Vive en **Cloudflare**.
- El proveedor real de WhatsApp es **Twilio**.
- El agente usa Claude API, FastAPI, SQLAlchemy y Twilio WhatsApp.
- La memoria conversacional vive en `agent/memory.py` y usa `DATABASE_URL`.
- Desarrollo local: SQLite (`agentkit.db`).
- Producción recomendada: Postgres externo vía `DATABASE_URL` — preferentemente Supabase o Neon — manteniendo Cloudflare como capa de despliegue/front/tunnel.
- El flujo “Reto 200 a 400” tiene dos referidos:
  - Normal / Leo: `https://client.ebccrm.com/signup?linkCode=U6913720-e01`
  - Maestro Josue / nuestro Josue: `https://client.myebc.co/signup?linkcode=F9090709-e01`
- Si el usuario menciona `Josue`, `Josué`, `maestro Josue` o `nuestro Josue` en el gatillo del reto, el agente debe usar el referido de Josue.
- Si no menciona Josue, el agente usa el referido normal de Leo.
- Los templates de Twilio/Meta registrados por `scripts/upload_twilio_templates.py` están aprobados al último chequeo local:
  - `leo_calificacion_inicial` — approved [MARKETING]
  - `leo_experiencia_previa` — approved [MARKETING]
  - `leo_herramientas` — approved [MARKETING]
  - `leo_capitalizar` — approved [MARKETING]
  - `leo_reto_paso1` — approved [MARKETING]
  - `leo_followup_sesion` — approved [UTILITY]

## Deploy a Producción

- **EC2 AWS IP:** 13.222.174.91
- **SSH:** `ssh -i leo-wa-key1.pem ubuntu@13.222.174.91`
- **Key local:** `/Users/jcarloschacon/Dev/leo-academia-trade/leo-wa-key1.pem`
- **Path en EC2:** `/home/ubuntu/whatsapp-agentkit`
- **Procedimiento completo:**
  1. Hacer cambios localmente
  2. `git push origin main`
  3. SSH al EC2: `cd /home/ubuntu/whatsapp-agentkit && git pull && docker compose up --build -d`
- **Knowledge update (sin rebuild):** Solo push a `knowledge/` → git pull en EC2 (volumen Docker monta esa carpeta automáticamente)
- **Dominio:** leoguadarrama.com (Cloudflare, plan Free, activo)
- **Cloudflare:** Tunnel/proxy hacia EC2

## Website (Landing Page)

- **Path local:** `/Users/jcarloschacon/Dev/leo-academia-trade/website/`
- **Stack:** Next.js 16 + Tailwind + shadcn + Framer Motion, `output: "export"`
- **Deploy:** `cd website && vercel --yes --prod`
- **Vercel project:** jcarloschaconherrera-4225s-projects/website
- **URL Vercel:** website-beryl-nine-91.vercel.app
- **Nota:** La carpeta website NO tiene su propio repo git

## Supabase

- **Project ref:** uiadgbcoitrwjrzsxayn
- **Edge Function:** `register-lead` (pública, sin JWT)
- **Tabla:** `public.leads` (id, nombre, email, whatsapp, fuente, maestro_ref, broker_link, metadata)
- **Endpoint:** `https://uiadgbcoitrwjrzsxayn.supabase.co/functions/v1/register-lead`

## Broker Links

- **Leo:** `https://client.ebccrm.com/signup?linkCode=U6913720-e01`
- **Josué:** `https://client.myebc.co/signup?linkcode=F9090709-e01`

## WhatsApp Links (Reto 200-400)

- **Leo:** `wa.me/527777934242?text=Hola, quiero el reto de 200 a 400. [ref:leo]`
- **Josué:** `wa.me/527777934242?text=Hola, me interesa el reto 200 a 400 con maestro Josué. [ref:josue]`

## Historial de Cambios

### 2026-05-16
- `config.ts` — retoAgente genera mensajes diferenciados Leo vs Josué
- `tools.py` — 3 frases trigger agregadas para detectar mensajes de la web
- Deploy: website a Vercel, agentkit a EC2 via git push + docker rebuild

## Claude-Mem

El usuario pidió activar `claude-mem` desde:

https://github.com/jcarloschaconherrera-alt/claude-mem.git

Estado de instalación local:

- Se intentó ejecutar `npx github:jcarloschaconherrera-alt/claude-mem install`, pero el paquete del fork no expuso el binario `claude-mem` para `npx`.
- Se instaló correctamente con `npx claude-mem install`.
- Se instaló Bun vía Homebrew para completar dependencias del worker.
- El worker se inició con `npx claude-mem start`.
- El fork del usuario quedó clonado localmente en `.claude-mem-source/` y está ignorado por Git.
- Datos locales de memoria: `~/.claude-mem`.
