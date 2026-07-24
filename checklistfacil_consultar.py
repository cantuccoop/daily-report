"""
Consulta checklists aplicados por dia no ChecklistFacil via API.
Usa cookies salvos pelo checklistfacil_login.py.
"""
import sys, json, os, requests
from datetime import datetime

DIR          = os.path.dirname(os.path.abspath(__file__))
COOKIES_FILE = os.path.join(DIR, "checklistfacil_spy.json")
API_BASE     = "https://app.checklistfacil.com.br/api/spa/v1"
HEADERS_BASE = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
    "Referer": "https://app.checklistfacil.com.br/",
}

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

def slug(nome):
    n = nome.lower().strip()
    for k, v in UNIDADE_MAP.items():
        if k in n:
            return v
    return None


def buscar_checklists(data_br=None):
    if not data_br:
        data_br = datetime.today().strftime("%d/%m/%Y")

    if not os.path.exists(COOKIES_FILE):
        print("  ChecklistFacil: sem cookies — rode checklistfacil_login.py")
        return []

    with open(COOKIES_FILE, encoding="utf-8") as f:
        spy = json.load(f)
    cookies = spy.get("cookies", {})
    if not cookies:
        print("  ChecklistFacil: cookies vazios")
        return []

    session = requests.Session()
    for k, v in cookies.items():
        session.cookies.set(k, v, domain="app.checklistfacil.com.br")
        session.cookies.set(k, v, domain=".checklistfacil.com.br")

    execucoes = []
    pagina = 1

    while True:
        params = {
            "status[]": "completed",
            "period": "start",
            "start_date": data_br,
            "end_date": data_br,
            "page": pagina,
            "per_page": 100,
            "my_analyses": 0,
        }
        try:
            r = session.get(f"{API_BASE}/evaluations", params=params,
                            headers=HEADERS_BASE, timeout=15)
        except Exception as e:
            print(f"  ChecklistFacil ERRO: {e}")
            break

        if r.status_code == 404:
            break
        if not r.ok:
            print(f"  ChecklistFacil: HTTP {r.status_code} — cookies expirados?")
            break

        try:
            data = r.json()
        except:
            break

        payload = data.get("data", data.get("payload", []))
        if not payload:
            break

        # data_br = "DD/MM/YYYY" → prefixo ISO "YYYY-MM-DD"
        data_iso = f"{data_br[6:10]}-{data_br[3:5]}-{data_br[0:2]}"
        encontrou_fora = False
        for item in payload:
            started = item.get("startedAt", "") or ""
            # Filtra pela data correta (API ignora start_date/end_date)
            if not started.startswith(data_iso):
                encontrou_fora = True
                continue
            unidade_nome   = (item.get("unit") or {}).get("name", "")
            checklist_nome = (item.get("checklist") or {}).get("name", "")
            score          = item.get("formattedScore", "")
            started_fmt    = started[:16].replace("T", " ")
            lid            = slug(unidade_nome)
            if unidade_nome and checklist_nome:
                execucoes.append({
                    "unidade":    unidade_nome,
                    "lid":        lid,
                    "checklist":  checklist_nome,
                    "data_hora":  started_fmt,
                    "nota":       score,
                })
        # Para quando não há mais itens do dia (API retorna decrescente)
        if encontrou_fora and not any(
            (item.get("startedAt") or "").startswith(data_iso) for item in payload
        ):
            break

        print(f"  Página {pagina}: {len(payload)} registros")
        if len(payload) < 100:
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
