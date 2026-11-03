"""Mide el portero con 80 avisos inventados y etiquetados a mano.

Es la bandeja del vídeo de modelos de decisión (repo devexpert-io/decision-models), así que
se puede comparar con lo que hizo Jev. La persona es Laura, que da cursos de programación.

    NAN_API_KEY=sk-... python3 eval/medir.py            # llama a NaN y guarda las respuestas
    python3 eval/medir.py --replay                      # otras reglas, sin llamar al modelo
    PORTERO_MODELO=qwen3.6 python3 eval/medir.py        # otro modelo
"""

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

AQUI = Path(__file__).parent
sys.path.insert(0, str(AQUI.parent / "scripts"))

import portero  # noqa: E402

PERSONA = "Laura, que da cursos de programación online"


def medir(senales: list[dict], registro: Path) -> list[dict]:
    registro.parent.mkdir(exist_ok=True)
    filas = []
    with registro.open("w") as f:
        for s in senales:
            inicio = time.time()
            t = portero.triar({k: s[k] for k in ("fuente", "de", "asunto", "texto")}, PERSONA)
            fila = {"id": s["id"], "respuesta": t, "segundos": round(time.time() - inicio, 2)}
            f.write(json.dumps(fila, ensure_ascii=False) + "\n")
            filas.append(fila)
            time.sleep(1)  # 60 peticiones por minuto y clave
    return filas


def informe(senales: list[dict], filas: list[dict]) -> None:
    por_id = {s["id"]: s for s in senales}
    avisa = [f for f in filas if portero.decidir(f["respuesta"]) != "ignorar"]
    falsas = [f for f in avisa if not por_id[f["id"]]["avisar"]]
    escapan = [f for f in filas if por_id[f["id"]]["avisar"] and f not in avisa]
    print(f"Modelo {portero.MODELO} · {len(filas)} avisos, {sum(s['avisar'] for s in senales)} merecen aviso")
    print(f"Avisos: {len(avisa)} · falsas alarmas: {len(falsas)} · se le escapan: {len(escapan)}")
    print(f"Mediana: {statistics.median(f['segundos'] for f in filas):.2f} s por aviso")
    for nombre, lista in (("Falsas alarmas", falsas), ("Se le escapan", escapan)):
        for f in lista:
            s = por_id[f["id"]]
            print(f"  {nombre}: #{s['id']} {s['asunto']} ({f['respuesta']['tipo']})")


def main() -> None:
    args = argparse.ArgumentParser()
    args.add_argument("--replay", action="store_true", help="reutiliza las respuestas guardadas")
    a = args.parse_args()

    senales = [json.loads(l) for l in (AQUI / "bandeja.jsonl").read_text().splitlines() if l.strip()]
    registro = AQUI / "runs" / f"{portero.MODELO}.jsonl"
    if a.replay:
        filas = [json.loads(l) for l in registro.read_text().splitlines()]
    else:
        filas = medir(senales, registro)
    informe(senales, filas)


if __name__ == "__main__":
    main()
