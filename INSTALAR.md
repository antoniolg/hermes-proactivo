# Instalación (instrucciones para Hermes)

Si eres Hermes y te han pedido instalar este repo, sigue estos pasos tal cual. No hace falta investigar nada más.

1. Comprueba que la skill `google-workspace` está conectada: `python <HERMES_HOME>/skills/productivity/google-workspace/scripts/setup.py --check` (si existe `<HERMES_HOME>/venv-google`, usa su Python) debe decir `AUTHENTICATED`. Si no, para y pide al usuario que conecte Gmail y Calendar primero.
2. Comprueba que hay canal de inicio en Telegram (el usuario ha mandado `/sethome`). Si no, pídeselo y espera.
3. Comprueba que `<HERMES_HOME>/.env` tiene una línea `NAN_API_KEY=` con valor. Si no, pide al usuario una clave de la API de NaN (la saca del panel de NaN) y añádela a ese fichero como `NAN_API_KEY=<clave>`. No la repitas en el chat. El portero la necesita porque Hermes no pasa su propia clave a los scripts del cron.
4. Clona el repo en la carpeta personal (si ya existe, `git pull`) y ejecuta `./setup.sh` desde dentro. Copia los scripts y el alma, configura la zona horaria y crea las rutinas `proactivo` y `reuniones`.
5. Lanza una primera pasada del portero para que marque como visto lo que ya hay en la bandeja: `hermes cron run proactivo` (si `hermes` no está en el PATH, usa `/opt/hermes/.venv/bin/hermes`).
6. Contesta al usuario en tres líneas: las dos rutinas creadas (con su horario), que la primera pasada ha terminado y que a partir de ahora le escribirás solo cuando algo merezca su atención.

No cambies nada del repo ni de su configuración, y no instales paquetes.
