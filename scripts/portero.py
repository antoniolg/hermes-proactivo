"""El portero: decide si merece la pena despertar al agente.

Hermes lo ejecuta antes de cada pasada de la rutina proactiva (`hermes cron create
--script portero.py`) y mete lo que imprime en el prompt del agente. Si la última
línea es {"wakeAgent": false}, el agente ni se despierta.

1. Sensores: los correos y los eventos nuevos, con la skill google-workspace.
2. Memoria: lo que ya ha visto no se vuelve a mirar.
3. Triaje: un modelo pequeño de NaN contesta preguntas cerradas sobre cada señal.
4. Reglas: decide el código, no el modelo.

Corre con el Python de Hermes, sin instalar nada: la biblioteca estándar y el yaml que ya trae Hermes.
"""

import functools
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

HERMES = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes"))
GAPI = HERMES / "skills/productivity/google-workspace/scripts/google_api.py"
ESTADO = HERMES / "scripts/.portero.json"

NAN_URL = "https://api.nan.builders/v1/chat/completions"
MODELO = os.environ.get("PORTERO_MODELO", "gemma4")  # sin contador de tokens
ZONA = ZoneInfo(os.environ.get("PORTERO_ZONA", "Europe/Madrid"))
PERSONA = os.environ.get(
    "PORTERO_PERSONA",
    "Antonio, fundador de DevExpert, una empresa de formación para desarrolladores",
)

# --- Las preguntas -------------------------------------------------------------------
# Cerradas y con criterios: el modelo elige, no redacta.

TIPOS = {
    "verificacion": "Un código de verificación o de doble factor, un aviso de inicio de sesión, un cambio de contraseña o un aviso de seguridad de la cuenta",
    "automatico": "Una notificación automática, un recibo, una newsletter, publicidad, una oferta comercial en frío (SEO, bases de datos, servicios que nadie ha pedido) o un mensaje de un sistema",
    "peticion": "Una persona (alumno, cliente, colaborador, proveedor, familia) que escribe y espera una respuesta, una decisión, un documento o que asista a algo",
    "oportunidad": "Una oportunidad de negocio concreta: un cliente potencial que pide algo, una formación, un patrocinio, una charla o una colaboración",
    "dinero": "Un problema con dinero: un cobro fallido, una suscripción cancelada, una factura vencida o una devolución",
    "plazo": "Un plazo o un requisito administrativo, fiscal, legal o de una plataforma",
    "propio": "Una tarea, una nota o un bloque de tiempo que esa persona o su asistente han escrito para sí",
    "reunion": "Una reunión, una llamada o un evento con otras personas",
    "otro": "Nada de lo anterior",
}
PASOS = {
    "asistente": "Un asistente con acceso al correo y al calendario puede hacerlo o prepararlo: redactar una respuesta, buscar información o reunir documentos",
    "persona": "Solo esa persona puede hacerlo: una llamada, una gestión en persona, firmar, pagar o una decisión personal",
    "nadie": "No hace falta ningún paso: es informativo, rutinario o ya está resuelto",
}
URGENCIA = ["Sin plazo o dentro de varias semanas", "En las próximas dos semanas", "Esta semana", "Hoy o mañana"]


def merece_avisar(persona: str) -> str:
    return (
        f"¿Debería un asistente personal avisar ahora a {persona}? Ya ve lo que provoca por su "
        "cuenta (códigos de verificación, inicios de sesión recientes, sus notas y sus bloques de "
        "tiempo) y las notificaciones rutinarias. Sí: es nuevo y hay algo que hacer, contestar o "
        "decidir, sea esa persona o el asistente. No: lo ha provocado esa persona, es rutinario o "
        "solo informa, o es una nota propia."
    )


def _lista(opciones: dict) -> str:
    return "\n".join(f"- {k}: {v}" for k, v in opciones.items())


def instrucciones(persona: str) -> str:
    return (
        "Eres el portero de un asistente personal proactivo. Lees un aviso (un correo, un evento o "
        "una tarea) y contestas preguntas cerradas. Responde solo con el JSON.\n\n"
        f"tipo: ¿qué tipo de aviso es?\n{_lista(TIPOS)}\n\n"
        f"avisar: {merece_avisar(persona)}\n\n"
        f"siguiente_paso: ¿quién puede dar el siguiente paso?\n{_lista(PASOS)}\n\n"
        "urgencia: ¿cuándo hay que atenderlo? "
        + "; ".join(f"{i} = {texto}" for i, texto in enumerate(URGENCIA))
    )


ESQUEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["tipo", "avisar", "siguiente_paso", "urgencia"],
    "properties": {
        "tipo": {"type": "string", "enum": list(TIPOS)},
        "avisar": {"type": "boolean"},
        "siguiente_paso": {"type": "string", "enum": list(PASOS)},
        "urgencia": {"type": "integer", "minimum": 0, "maximum": 3},
    },
}

# --- Las reglas ----------------------------------------------------------------------
# Viven en el código, no en el prompt: se pueden leer, probar y cambiar sin tocar el modelo.

NUNCA = {"verificacion", "propio"}  # lo provoca él mismo
SILENCIO = (23, 8)  # de 23:00 a 8:00 solo pasa lo urgente
AVISOS_AL_DIA = 8


def decidir(t: dict) -> str:
    """Convierte las respuestas del portero en una acción: preparar, avisar o ignorar."""
    if t["tipo"] in NUNCA or not t["avisar"]:
        return "ignorar"
    return "preparar" if t["siguiente_paso"] == "asistente" else "avisar"


# --- El modelo -----------------------------------------------------------------------


@functools.cache
def nan_key() -> str:
    """NAN_API_KEY si está; si no, la clave con la que el propio Hermes llama a NaN."""
    if key := os.environ.get("NAN_API_KEY"):
        return key
    for bloque in _bloques_config():
        if "nan.builders" in str(bloque.get("base_url") or bloque.get("api") or ""):
            if key := bloque.get("api_key") or os.environ.get(bloque.get("key_env") or ""):
                return key
    sys.exit("No encuentro la clave de NaN: añade NAN_API_KEY a ~/.hermes/.env")


def _bloques_config() -> list[dict]:
    """Todos los diccionarios de ~/.hermes/config.yaml: la URL y la clave pueden estar en varios sitios."""
    try:
        import yaml  # viene con Hermes

        pendientes = [yaml.safe_load((HERMES / "config.yaml").read_text())]
    except Exception:
        return []
    bloques = []
    while pendientes:
        x = pendientes.pop()
        if isinstance(x, dict):
            bloques.append(x)
            pendientes.extend(x.values())
        elif isinstance(x, list):
            pendientes.extend(x)
    return bloques


def triar(senal: dict, persona: str = PERSONA, modelo: str = MODELO) -> dict:
    """Una llamada por señal: cuatro respuestas cerradas, con la forma que exige el esquema."""
    cuerpo = {
        "model": modelo,
        "reasoning_effort": "none",
        "temperature": 0,
        "max_tokens": 80,  # el JSON cabe de sobra; corta si el modelo se pone a rellenar
        "messages": [
            {"role": "system", "content": instrucciones(persona)},
            {"role": "user", "content": json.dumps(senal, ensure_ascii=False)},
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": "portero", "strict": True, "schema": ESQUEMA},
        },
    }
    return json.loads(_post(cuerpo)["choices"][0]["message"]["content"])


def _post(cuerpo: dict) -> dict:
    peticion = urllib.request.Request(
        NAN_URL,
        data=json.dumps(cuerpo).encode(),
        headers={"Authorization": f"Bearer {nan_key()}", "Content-Type": "application/json"},
    )
    for intento in range(3):
        try:
            with urllib.request.urlopen(peticion, timeout=60) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code != 429 or intento == 2:  # 60 peticiones por minuto y clave
                raise
            time.sleep(10 * (intento + 1))
    raise RuntimeError("inalcanzable")


# --- Los sensores --------------------------------------------------------------------


def gapi(*args: str) -> list[dict]:
    """Llama a la skill google-workspace de Hermes y devuelve su JSON."""
    # Si el venv de Hermes es de solo lectura (en NaN lo es), la skill instala Google en venv-google
    python = HERMES / "venv-google/bin/python"
    salida = subprocess.run(
        [str(python) if python.exists() else sys.executable, str(GAPI), *args],
        capture_output=True, text=True, check=True, timeout=120,
    )
    return json.loads(salida.stdout or "[]")


def correos_nuevos() -> list[dict]:
    return [
        {
            "id": c["id"],
            "fuente": "correo",
            "de": c["from"],
            "asunto": c["subject"],
            "texto": c["snippet"],
            "hilo": c["threadId"],
        }
        for c in gapi("gmail", "search", "in:inbox -from:me newer_than:2d", "--max", "25")
    ]


def eventos_nuevos() -> list[dict]:
    ahora = datetime.now(timezone.utc)
    eventos = gapi(
        "calendar", "list", "--start", ahora.isoformat(), "--end", (ahora + timedelta(hours=36)).isoformat()
    )
    return [
        {
            "id": e["id"],
            "fuente": "calendario",
            "de": "",
            "asunto": e["summary"],
            "texto": f"Empieza: {e['start']}. {e['location']} {e['description']}".strip()[:600],
        }
        for e in eventos
        if e.get("status") != "cancelled"
    ]


# --- La pasada -----------------------------------------------------------------------


def main() -> None:
    estado = json.loads(ESTADO.read_text()) if ESTADO.exists() else None
    senales = correos_nuevos() + eventos_nuevos()

    if estado is None:
        # Primera pasada: lo que ya estaba no es noticia
        guardar({"vistas": {s["id"]: time.time() for s in senales}, "avisos": []})
        print(f"Primera pasada: {len(senales)} señales marcadas como vistas.")
        print(json.dumps({"wakeAgent": False}))
        return

    vistas = estado["vistas"]  # id → cuándo se vio
    esperando = estado.get("esperando", {})  # triadas durante el silencio
    ahora = datetime.now(ZONA)
    hoy = [a for a in estado["avisos"] if a > (ahora - timedelta(days=1)).timestamp()]
    silencio = ahora.hour >= SILENCIO[0] or ahora.hour < SILENCIO[1]

    pasan = []
    for s in senales:
        if s["id"] in vistas:
            continue
        t = esperando.pop(s["id"], None) or triar({k: s[k] for k in ("fuente", "de", "asunto", "texto")})
        accion = decidir(t)
        if accion != "ignorar" and silencio and t["urgencia"] < 3:
            esperando[s["id"]] = t  # se avisa al acabar el silencio, sin volver a preguntar
            continue
        vistas[s["id"]] = time.time()
        if accion != "ignorar":
            pasan.append((s, t, accion))

    despertar = bool(pasan) and len(hoy) < AVISOS_AL_DIA
    if despertar:
        hoy.append(ahora.timestamp())
    else:
        for s, t, _ in pasan:  # sin presupuesto hoy: esperan, no se pierden
            vistas.pop(s["id"], None)
            esperando[s["id"]] = t
    actuales = {s["id"] for s in senales}
    esperando = {k: v for k, v in esperando.items() if k in actuales}
    hace_tres_dias = time.time() - 3 * 86400  # más que la ventana de los sensores
    vistas = {k: v for k, v in vistas.items() if v > hace_tres_dias}
    guardar({"vistas": vistas, "avisos": hoy, "esperando": esperando})

    if not despertar:
        print(json.dumps({"wakeAgent": False}))
        return
    print("Señales que merecen tu atención (el portero ya ha descartado el resto):\n")
    for n, (s, t, accion) in enumerate(pasan, 1):
        print(f"{n}. [{accion} · {t['tipo']} · urgencia {t['urgencia']}] {s['fuente']} «{s['asunto']}» de {s['de'] or '-'}")
        print(f"   id: {s['id']}" + (f" · hilo: {s['hilo']}" if s.get("hilo") else ""))
        print(f"   {s['texto'][:300]}\n")
    print(json.dumps({"wakeAgent": True}))


def guardar(estado: dict) -> None:
    ESTADO.write_text(json.dumps(estado))


if __name__ == "__main__":
    main()
