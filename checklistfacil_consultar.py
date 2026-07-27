"""
Consulta checklists aplicados por dia no ChecklistFacil.
Tenta primeiro via cookies (endpoint interno com filtro de data).
Se cookies expirados, usa API Analytics com paginação inteligente.
"""
import sys, json, os, requests, time
from datetime import datetime, date
from collections import Counter

DIR          = os.path.dirname(os.path.abspath(__file__))
COOKIES_FILE = os.path.join(DIR, "checklistfacil_spy.json")
API_KEY      = os.environ.get("CHECKLIST_API_KEY",
               "EzHmDeA9R2Mje3dBS8FRzzq0WXQTEgvknraebBy0IIh8aH9uKOaxaD7Ez2HTHQ9wPFDNQa3L1xxIAN6LXYYR0Qx5B9bLdvUhy5iPSvFy8Kzyq79dwI2VqjjD09L0IlCO")
INTERNAL_URL = "https://app.checklistfacil.com.br/api/spa/v1/evaluations"
ANALYTICS_URL = "https://api-analytics.checklistfacil.com.br/v1/evaluations"

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


# ── Método 1: endpoint interno com cookies (filtra data no servidor) ──────────
def buscar_via_cookies(data_br, data_iso):
    if not os.path.exists(COOKIES_FILE):
        return None

    with open(COOKIES_FILE, encoding="utf-8") as f:
        spy = json.load(f)
    cookies = spy.get("cookies", {})
    if not cookies:
        return None

    session = requests.Session()
    for k, v in cookies.items():
        session.cookies.set(k, v, domain="app.checklistfacil.com.br")
        session.cookies.set(k, v, domain=".checklistfacil.com.br")

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json",
        "Referer": "https://app.checklistfacil.com.br/",
    }

    execucoes = []
    pagina = 1
    while True:
        params = {"status[]": "completed", "period": "start",
                  "start_date": data_br, "end_date": data_br,
                  "page": pagina, "per_page": 100, "my_analyses": 0}
        try:
            r = session.get(INTERNAL_URL, params=params, headers=headers, timeout=15)
        except Exception:
            return None

        if r.status_code == 401:
            return None  # cookies expirados
        if not r.ok:
            return None

        items = r.json().get("data", r.json().get("payload", []))
        if not items:
            break

        for item in items:
            started = item.get("startedAt", "") or ""
            if not started.startswith(data_iso):
                if any(ex["data_hora"][:10] != data_iso for ex in execucoes):
                    break
                continue
            unidade_nome   = (item.get("unit") or {}).get("name", "")
            checklist_nome = (item.get("checklist") or {}).get("name", "")
            score          = item.get("formattedScore", "")
            lid            = slug(unidade_nome)
            if unidade_nome and checklist_nome:
                execucoes.append({"unidade": unidade_nome, "lid": lid,
                                  "checklist": checklist_nome,
                                  "data_hora": started[:16].replace("T", " "),
                                  "nota": score})

        print(f"  [cookies] Página {pagina}: {len(items)} registros")
        if len(items) < 100:
            break
        pagina += 1

    return execucoes


# ── Método 2: API Analytics com paginação inteligente ────────────────────────
# Referência calibrada: página 18 = jul/2026
# A API retorna dados em ordem crescente; total sempre 0 (bug da API)
_REF_PAG  = 18
_REF_DATA = date(2026, 7, 1)
_PAG_MES  = 1.6   # páginas por mês (calibrado em jul/2026)

# Mapa fixo de unitId → lid (obtido via /v1/units)
_UNIT_ID_MAP = {
    3895613: "cantucci_an",
    3895614: "cantucci_ac",
    3895616: "cantucci_as",
    3895617: "superquadra",
    3895618: "mane",
    3895619: "mane",
    4329290: "koji",
}

def _estimar_pagina(data_iso):
    alvo = date.fromisoformat(data_iso)
    meses = (alvo.year - _REF_DATA.year) * 12 + (alvo.month - _REF_DATA.month)
    return max(1, int(_REF_PAG + meses * _PAG_MES))

def _fetch_pag(headers, pag):
    time.sleep(2.5)  # respeita rate limit ~1-2 req/min
    try:
        r = requests.get(ANALYTICS_URL,
                         params={"page": pag, "limit": 1000}, headers=headers, timeout=25)
        if r.status_code == 429:
            print(f"  [apikey] Rate limit na pag {pag} — aguardando 30s")
            time.sleep(30)
            r = requests.get(ANALYTICS_URL,
                             params={"page": pag, "limit": 1000}, headers=headers, timeout=25)
        if not r.ok:
            print(f"  [apikey] Erro HTTP {r.status_code} na pag {pag}")
            return None
        return r.json().get("data", [])
    except Exception as e:
        print(f"  [apikey] Exceção na pag {pag}: {e}")
        return None

def _item_para_exec(item):
    started = item.get("startedAt", "") or ""
    uid   = item.get("unitId")
    lid   = _UNIT_ID_MAP.get(uid)
    uname = {v: k for k, v in UNIDADE_MAP.items()}.get(lid, str(uid)) if lid else str(uid)
    return {"unidade": uname, "lid": lid,
            "checklist": str(item.get("checklistId", "")),
            "data_hora": started[:16].replace("T", " "),
            "nota": str(item.get("score") or "")}

def buscar_via_apikey(data_iso):
    headers = {"Authorization": f"Bearer {API_KEY}", "Accept": "application/json"}
    estimada = _estimar_pagina(data_iso)
    print(f"  [apikey] Data alvo: {data_iso} | Página estimada: {estimada}")

    execucoes = []
    # Varre da página estimada-2 até estimada+5 (margem de ±30%)
    for pag in range(max(1, estimada - 2), estimada + 6):
        items = _fetch_pag(headers, pag)
        if items is None:
            break
        if not items:
            print(f"  [apikey] Pág {pag}: vazia — fim dos dados")
            break

        primeira = (items[0].get("startedAt", "") or "")[:10]
        ultima   = (items[-1].get("startedAt", "") or "")[:10]
        do_dia   = [i for i in items if (i.get("startedAt", "") or "").startswith(data_iso)]
        print(f"  [apikey] Pág {pag}: {primeira} → {ultima} | {len(do_dia)} registros de {data_iso}")

        for item in do_dia:
            execucoes.append(_item_para_exec(item))

        # Parar se já passamos da data alvo
        if ultima > data_iso:
            break

    return execucoes if execucoes else None


# ── Principal ─────────────────────────────────────────────────────────────────
def buscar_checklists(data_br=None):
    if not data_br:
        data_br = datetime.today().strftime("%d/%m/%Y")
    data_iso = f"{data_br[6:10]}-{data_br[3:5]}-{data_br[0:2]}"

    # Tenta cookies primeiro (mais preciso)
    resultado = buscar_via_cookies(data_br, data_iso)
    if resultado is not None:
        print(f"  ChecklistFácil via cookies: {len(resultado)} execuções")
        return resultado

    print("  Cookies expirados — tentando API key...")
    resultado = buscar_via_apikey(data_iso)
    if resultado is not None:
        print(f"  ChecklistFácil via API key: {len(resultado)} execuções")
        return resultado

    print("  ChecklistFácil: sem acesso disponível")
    return []


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
