# Hermes proactivo

Un asistente personal que te escribe antes de que le preguntes, como Muse de Meta o los Dots de OpenAI, pero en una máquina tuya y con modelos que no guardan lo que les mandas.

Vigila tu correo y tu calendario. Cuando algo necesita tu atención, prepara el trabajo (lee el hilo, redacta la respuesta) y te escribe por Telegram con una pregunta: «¿Se lo envío así?».

```
sensores ─▶ portero ─▶ agente ─▶ Telegram
Gmail y      un modelo    el modelo     «Te ha escrito Laura…
Calendar     pequeño      grande        ¿Se lo envío así?»
             decide si    prepara
             merece la    el trabajo
             pena
```

Todo corre en [NaN](https://cloud.nan.builders/r/067T5405): el agente ([Hermes](https://hermes-agent.nousresearch.com), de Nous Research) en un workspace, que es una máquina en la nube solo tuya, y los modelos en su clúster de la Unión Europea, que no guarda prompts ni respuestas.

## Requisitos

- Un plan de NaN con inferencia y un workspace con Hermes. El plan premium incluye un workspace Micro; con el de 70 € al mes, un slot Micro cuesta 4,99 € al mes.
- Un bot de Telegram: créalo con [@BotFather](https://t.me/BotFather) y guarda el token.
- Una cuenta de Google y un cliente OAuth de escritorio en [Google Cloud](https://console.cloud.google.com/apis/credentials), con las APIs de Gmail y Calendar activadas.

## Paso a paso

Cada paso tiene su tag (`git checkout paso-1`).

| Paso | Qué haces | Dónde |
|---|---|---|
| 1 | Crear el workspace con Hermes, conectarle Telegram y darle personalidad | [`soul/SOUL.md`](soul/SOUL.md) |
| 2 | Darle acceso a tu correo y tu calendario | La skill `google-workspace` de Hermes |
| 3 | El portero: un modelo pequeño contesta preguntas cerradas y el código decide | [`scripts/portero.py`](scripts/portero.py) y [`eval/medir.py`](eval/medir.py) |
| 4 | Las rutinas: cada 15 minutos mira si hay algo y cada tarde prepara las reuniones de mañana | [`setup.sh`](setup.sh) y [`prompts/`](prompts) |

### 1 · El workspace

En [cloud.nan.builders/workspaces](https://cloud.nan.builders/workspaces), crea un workspace y marca Hermes. En su configuración elige el modelo (`deepseek-v4-flash`), pega el token de Telegram, pon tu ID de Telegram (te lo da [@userinfobot](https://t.me/userinfobot)) y, como alma, el contenido de [`soul/SOUL.md`](soul/SOUL.md). No dejes vacío el ID: sin él, el bot contesta a cualquiera.

Si ya lo creaste sin el ID: tal como viene en el workspace, Hermes arranca con `GATEWAY_ALLOW_ALL_USERS=true`, así que contesta a cualquiera que encuentre el bot, con una terminal en tu máquina detrás. Antes de darle tu correo, ciérralo a tu usuario. Se hace desde el propio chat:

1. Manda `/whoami`: te contesta con tu ID de Telegram.
2. Pídeselo: «Haz que solo pueda hablarte yo: añade `TELEGRAM_ALLOWED_USERS=<tu ID>` a `~/.hermes/.env`». Si te pide permiso para tocar el archivo, apruébalo.
3. Manda `/restart` para que lo cargue. Si en un minuto no vuelve a contestar, para y arranca el workspace desde el panel.

Con una lista de usuarios, el permiso para todos deja de aplicarse y Hermes ignora a los desconocidos. Compruébalo escribiéndole desde otra cuenta: no debería contestar.

Y en el chat con el bot, `/sethome`: ahí llegarán los avisos.

En el workspace, Hermes está en `/opt/hermes` y no en el PATH. Para usar `hermes` en la consola:

```bash
echo 'export PATH=/opt/hermes/.venv/bin:$PATH' >> ~/.bashrc && source ~/.bashrc
```

### 2 · Correo y calendario

Pídeselo por Telegram: «Conéctate a mi Gmail y a mi calendario». La skill `google-workspace` te guía: le pasas el JSON del cliente OAuth, te manda un enlace, lo autorizas y le pegas la dirección a la que te lleva el navegador. Pide solo los permisos de correo y calendario.

### 3 · El portero

Sin él, la rutina despertaría al modelo grande cada 15 minutos para no encontrar nada. Con él, un modelo pequeño (`gemma4`, sin contador de tokens en NaN) contesta cuatro preguntas cerradas sobre cada correo o evento nuevo:

- qué tipo de aviso es (verificación, automático, petición, oportunidad, dinero, plazo, propio, reunión u otro);
- si merece la pena avisar;
- quién puede dar el siguiente paso;
- y lo urgente que es.

Las respuestas llegan con la forma exacta de un esquema JSON (`json_schema` estricto), así que el código las lee sin sorpresas. Y las reglas están en el código (`decidir`): lo que provocas tú nunca pasa, de 23:00 a 8:00 solo pasa lo urgente y hay un máximo de avisos al día. Si nada pasa, el script termina con `{"wakeAgent": false}` y Hermes no despierta al agente.

Para medirlo, la bandeja de 80 avisos etiquetados a mano del vídeo de [modelos de decisión](https://github.com/devexpert-io/decision-models):

```bash
NAN_API_KEY=sk-... python3 eval/medir.py           # llama a NaN y guarda las respuestas
python3 eval/medir.py --replay                     # otras reglas, sin llamar al modelo
```

El 3 de noviembre de 2026, con `gemma4`: 37 avisos, ninguna falsa alarma y no se le escapa ninguno, a 1,2 segundos por aviso. Con la primera versión del criterio salían dos falsas alarmas, dos ofertas comerciales en frío; una línea más en la definición de «automático» las quitó. Como el criterio se afinó con esta misma bandeja, pruébalo también con la tuya.

### 4 · Las rutinas

Con Hermes funcionando, el correo conectado y `/sethome` hecho, pídeselo por Telegram:

> Instala https://github.com/antoniolg/hermes-proactivo siguiendo su INSTALAR.md

[`INSTALAR.md`](INSTALAR.md) son las instrucciones para el agente. Antes de pedirle a un agente que instale algo, lee lo que va a ejecutar: aquí, `setup.sh`.

O hazlo tú en la consola del workspace:

```bash
git clone https://github.com/antoniolg/hermes-proactivo
cd hermes-proactivo && ./setup.sh
```

Copia los scripts y el alma a `~/.hermes` y crea dos rutinas de Hermes:

- `proactivo`, cada 15 minutos: el portero filtra y, si algo pasa, el agente lo prepara y te escribe. Al contestarle («sí, envíalo»), la conversación sigue en el hilo del aviso.
- `reuniones`, cada día a las 18:00: un resumen de cada reunión de mañana con lo que sabe por tu correo.

Para no esperar a la siguiente pasada: `hermes cron run proactivo`.

El portero llama a NaN con la clave `NAN_API_KEY` de `~/.hermes/.env`. Hermes no pasa su propia clave a los scripts del cron, así que la instalación te pide una (la sacas del panel de NaN) y la guarda ahí.

## Límites

- La clave de NaN admite 60 peticiones por minuto: el portero hace una por señal nueva y reintenta si se pasa.
- El correo sigue estando en Google. Lo que no sale del workspace y de NaN es lo que el asistente lee, piensa y escribe sobre él.
- La red del workspace solo deja salir por los puertos 80, 443 y 22: el correo va por la API de Gmail, no por IMAP ni SMTP.

## Licencia

MIT
