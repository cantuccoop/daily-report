"""
Consulta checklists aplicados por dia no ChecklistFacil via API Analytics.
Usa API key permanente — sem necessidade de cookies ou login manual.
"""
import sys, json, os, requests
from datetime import datetime

DIR      = os.path.dirname(os.path.abspath(__file__))
API_KEY  = os.environ.get("CHECKLIST_API_KEY",
           "EzHmDeA9R2Mje3dBS8FRzzq0WXQTEgvknraebBy0IIh8aH9uKOaxaD7Ez2HTHQ9wPFDNQa3L1xxIAN6LXYYR0Qx5B9bLdvUhy5iPSvFy8Kzyq79dwI2VqjjD09L0IlCO")
BASE     = "https://api-analytics.checklistfacil.com.br/v1"
HEADERS  = {"Authorization": f"Bearer {API_KEY}", "Accept": "application/json"}

UNIDADE_MAP = {
    "cantucci asa sul":      "cantucci_as",
    "cantucci asa norte":    "cantucci_an",
    "cantucci aguas claras": "cantucci_ac",
    "cantucci águas claras": "cantucci_ac",
    "superquadra norte":     "superquadra",
    "mané":                  "mane",
    "mane":                  "mane",
    "véi chico":             "mane",
    "vei chico":             "mane",
    "koji":                  "koji",
}

_units_cache = {}

def get_units():
    if _units_cache:
        return _units_cache
    r = requests.get(f"{BASE}/units", headers=HEADERS, timeout=15)
    if not r.ok:
        return {}
    for u in r.json().get("data", []):
        _units_cache[u["unitId"]] = u.get("name", "")
    return _units_cache

def slug(nome):
    n = nome.lower().strip()
    for k, v in UNIDADE_MAP.items():
        if k in n:
            return v
    return None


def buscar_checklists(data_br=None):
    if not data_br:
        data_br = datetime.today().strftime("%d/%m/%Y")

    # Converte DD/MM/YYYY → YYYY-MM-DD
    data_iso = f"{data_br[6:10]}-{data_br[3:5]}-{data_br[0:2]}"

    units = get_units()

    execucoes = []
    pagina = 1

    while True:
        params = {
            "page":      pagina,
            "limit":     1000,
            "status":    6,          # 6 = concluído
            "startDate": data_iso,
            "endDate":   data_iso,
        }
        try:
            r = requests.get(f"{BASE}/evaluations", params=params,
                             headers=HEADERS, timeout=20)
        except Exception as e:
            print(f"  ChecklistFacil ERRO: {e}")
            break

        if not r.ok:
            print(f"  ChecklistFacil: HTTP {r.status_code}")
            break

        data = r.json()
        items = data.get("data", [])
        if not items:
            break

        print(f"  Página {pagina}: {len(items)} registros")

        for item in items:
            uid   = item.get("unitId")
            nome  = units.get(uid, str(uid))
            lid   = slug(nome)
            score = item.get("score")
            started = item.get("startedAt", "")[:16].replace("T", " ") if item.get("startedAt") else ""
            if nome:
                execucoes.append({
                    "unidade":   nome,
                    "lid":       lid,
                    "checklist": str(item.get("checklistId", "")),
                    "data_hora": started,
                    "nota":      str(score) if score is not None else "",
                })

        total = data.get("total") or data.get("count") or 0
        if len(execucoes) >= total or len(items) < 1000:
            break
        pagina += 1

    return execucoes


def main():
    data = sys.argv[1] if len(sys.argv) > 1 else datetime.today().strftime("%d/%m/%Y")
    print(f"\n  Buscando checklists de {data}...")
    execucoes = buscar_checklists(data)
    resultado = {"data": data, "total": len(execucoes), "execucoes": execucoes}
    out = os.path.join(DIR, "checklistfacil_resultado.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(resultado, f, ensure_ascii=False, indent=2)
    print(f"  Total: {len(execucoes)} execuções salvas")


main()
