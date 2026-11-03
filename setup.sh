#!/usr/bin/env bash
# Convierte el Hermes de este workspace en un asistente proactivo.
#
# Antes: Hermes contesta por Telegram, has mandado /sethome en ese chat (paso 1),
# Google está conectado (paso 2) y ~/.hermes/.env tiene NAN_API_KEY, la clave con
# la que el portero llama a NaN (Hermes no pasa la suya a los scripts del cron).
set -euo pipefail
cd "$(dirname "$0")"
H="${HERMES_HOME:-$HOME/.hermes}"

if ! grep -q '^NAN_API_KEY=.' "$H/.env" 2>/dev/null; then
  echo "Falta NAN_API_KEY en $H/.env: es la clave con la que el portero llama a NaN." >&2
  exit 1
fi
# En los workspaces de NaN, Hermes vive en /opt/hermes y no está en el PATH
HERMES="$(command -v hermes || echo /opt/hermes/.venv/bin/hermes)"

# El portero y la rutina de reuniones, donde Hermes busca los scripts
mkdir -p "$H/scripts"
cp scripts/portero.py scripts/reuniones.py "$H/scripts/"

# La personalidad (se guarda la que hubiera)
if [ -f "$H/SOUL.md" ]; then cp "$H/SOUL.md" "$H/SOUL.md.antes"; fi
cp soul/SOUL.md "$H/SOUL.md"

# Las horas de las rutinas van en tu zona, y al contestar a un aviso
# la conversación sigue en su hilo, con el aviso delante
"$HERMES" config set timezone Europe/Madrid
"$HERMES" config set cron.mirror_delivery true

# Cada 15 minutos mira si hay algo; el portero decide si el agente se despierta
"$HERMES" cron create "every 15m" "$(cat prompts/proactivo.md)" \
  --name proactivo --script portero.py --skill google-workspace \
  --deliver telegram --continuity

# Cada tarde, el resumen de las reuniones de mañana
"$HERMES" cron create "0 18 * * *" "$(cat prompts/reuniones.md)" \
  --name reuniones --script reuniones.py --skill google-workspace \
  --deliver telegram

"$HERMES" cron list
