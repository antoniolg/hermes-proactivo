"""Las reuniones de mañana: el portero elige cuáles merecen un resumen.

Va con la rutina de las 18:00 (`hermes cron create "0 18 * * *" ... --script reuniones.py`).
Si mañana no hay reuniones con otras personas, el agente no se despierta.
"""

import json
from datetime import datetime, timedelta

from portero import ZONA, gapi, triar


def main() -> None:
    manana = datetime.combine(datetime.now(ZONA).date() + timedelta(days=1), datetime.min.time(), ZONA)
    eventos = gapi("calendar", "list", "--start", manana.isoformat(), "--end", (manana + timedelta(days=1)).isoformat())

    reuniones = []
    for e in eventos:
        if e.get("status") == "cancelled" or "T" not in e["start"]:  # sin hora: es de día entero
            continue
        texto = f"{e['description']} {e['location']}".strip()[:600]
        if triar({"fuente": "calendario", "de": "", "asunto": e["summary"], "texto": texto})["tipo"] == "reunion":
            reuniones.append(e)

    if not reuniones:
        print(json.dumps({"wakeAgent": False}))
        return
    print("Reuniones de mañana con otras personas:\n")
    for e in reuniones:
        print(f"- {e['start'][11:16]} «{e['summary']}» {e['location']}".rstrip())
        if e["description"]:
            print(f"  {e['description'][:300]}")
    print(json.dumps({"wakeAgent": True}))


if __name__ == "__main__":
    main()
