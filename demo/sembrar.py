"""Siembra una cuenta de Google de demo: correos de relleno, un hilo con Marta y la llamada de mañana.

Mete los correos con la API de Gmail (`messages.insert`), sin enviar nada: el remitente y la
fecha son los que pone aquí. Usa el token de la skill google-workspace de Hermes, así que se
ejecuta en el workspace después de conectar Google (paso 2) y antes de la primera pasada del
portero, que marcará todo esto como visto:

    python demo/sembrar.py

Con el Python que tenga las librerías de Google (el venv donde las instaló la skill).
"""

import base64
import os
from datetime import datetime, timedelta
from email.message import EmailMessage
from email.utils import format_datetime, make_msgid
from pathlib import Path
from zoneinfo import ZoneInfo

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

HERMES = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes"))
ZONA = ZoneInfo("Europe/Madrid")
AHORA = datetime.now(ZONA)

RELLENO = [
    ("Python Weekly <newsletter@pythonweekly.example>", "Python Weekly #712",
     "Esta semana: el nuevo JIT de CPython, cinco librerías para validar datos y una charla sobre asyncio.", 3),
    ("Google <no-reply@accounts.google.example>", "Código de verificación",
     "Tu código de verificación es 482913. Caduca en 10 minutos. No lo compartas con nadie.", 2),
    ("Hetzner Online <billing@hetzner.example>", "Tu factura de octubre",
     "Ya tienes disponible la factura de octubre: 23,40 €. Se cobrará en tu tarjeta en los próximos días.", 2),
    ("Carlos Ruiz <carlos@seo-rapido.example>", "Primera página de Google en 30 días",
     "Hola, he visto tu web y creo que podría posicionar mucho mejor. Garantizamos primera página en 30 días. ¿Hablamos?", 1),
]


def correo(de: str, para: str, asunto: str, texto: str, fecha: datetime, **cabeceras) -> dict:
    m = EmailMessage()
    m["From"], m["To"], m["Subject"], m["Date"] = de, para, asunto, format_datetime(fecha)
    m["Message-ID"] = make_msgid(domain="demo.example")
    for k, v in cabeceras.items():
        m[k.replace("_", "-")] = v
    m.set_content(texto)
    return {"raw": base64.urlsafe_b64encode(m.as_bytes()).decode(), "_id": m["Message-ID"]}


def meter(gmail, mensaje: dict, etiquetas: list[str], hilo: str | None = None) -> dict:
    cuerpo = {"raw": mensaje["raw"], "labelIds": etiquetas}
    if hilo:
        cuerpo["threadId"] = hilo
    return gmail.users().messages().insert(userId="me", body=cuerpo, internalDateSource="dateHeader").execute()


def main() -> None:
    creds = Credentials.from_authorized_user_file(str(HERMES / "google_token.json"))
    gmail, calendario = build("gmail", "v1", credentials=creds), build("calendar", "v3", credentials=creds)
    yo = gmail.users().getProfile(userId="me").execute()["emailAddress"]

    for de, asunto, texto, dias in RELLENO:
        meter(gmail, correo(de, yo, asunto, texto, AHORA - timedelta(days=dias)), ["INBOX"])

    # El hilo con Marta: ella pide, tú contestas y queda pendiente el temario
    marta = "Marta López <marta@fintechx.example>"
    pide = correo(marta, yo, "Formación de IA para mi equipo",
                  "Hola, Antonio: soy CTO de Fintech X. Queremos formar en IA a nuestro equipo de 12 "
                  "desarrolladores antes de final de año. ¿Hacéis formaciones para empresas? ¿Podemos hablar?",
                  AHORA - timedelta(days=6))
    hilo = meter(gmail, pide, ["INBOX"])["threadId"]
    meter(gmail, correo(yo, marta, "Re: Formación de IA para mi equipo",
                        "Hola, Marta: sí, claro. Te propongo una llamada el día que te venga bien y antes te "
                        "mando el temario para que lo vea tu equipo.",
                        AHORA - timedelta(days=5), In_Reply_To=pide["_id"], References=pide["_id"]),
          ["SENT"], hilo)

    manana = (AHORA + timedelta(days=1)).replace(hour=10, minute=0, second=0, microsecond=0)
    calendario.events().insert(calendarId="primary", sendUpdates="none", body={
        "summary": "Llamada con Marta (Fintech X)",
        "description": "Formación de IA para su equipo de 12 desarrolladores.",
        "start": {"dateTime": manana.isoformat()},
        "end": {"dateTime": (manana + timedelta(minutes=45)).isoformat()},
    }).execute()

    print(f"Sembrada {yo}: {len(RELLENO)} correos de relleno, el hilo con Marta y la llamada de mañana a las 10:00.")


if __name__ == "__main__":
    main()
