"""
Busca checklists retroativos e injeta no HISTORICO_MATURIDADE.json (lista de registros).
"""
import sys, json, os, subprocess
from datetime import date, timedelta
from collections import defaultdict

DIR = os.path.dirname(os.path.abspath(__file__))
HIST_FILE   = os.path.join(DIR, "HISTORICO_MATURIDADE.json")
RESULT_FILE = os.path.join(DIR, "checklistfacil_resultado.json")

CHECKLIST_ESPERADO = {
    'cantucci_an':  8,
    'cantucci_as':  12,
    'cantucci_ac':  12,
    'superquadra':  14,
    'mane':         12,
    'koji':         4,
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

def buscar_counts(data_iso):
    data_br = f"{data_iso[8:10]}/{data_iso[5:7]}/{data_iso[0:4]}"
    subprocess.run(
        [sys.executable, "checklistfacil_consultar.py", data_br],
        cwd=DIR, capture_output=True, text=True, timeout=120,
        encoding="utf-8", errors="replace"
    )
    if not os.path.exists(RESULT_FILE):
        return None
    with open(RESULT_FILE, encoding="utf-8") as f:
        raw = json.load(f)
    if raw.get("data") != data_br:
        return None
    counts = {}
    for ex in raw.get("execucoes", []):
        lid = ex.get("lid") or slug(ex.get("unidade", ""))
        if lid:
            counts[lid] = counts.get(lid, 0) + 1
    return counts

def recalcular_score(rec, ck_exec):
    q = rec.get("quadro_turnos", 0)
    r = rec.get("relatorio_turnos", 0)
    ck_esp = CHECKLIST_ESPERADO.get(rec["unidade_id"], 4)
    q_s  = min(q / 2, 1.0) * 10
    r_s  = min(r / 2, 1.0) * 10
    ck_s = min(ck_exec / ck_esp, 1.0) * 10 if ck_exec > 0 else None
    if ck_s is not None:
        score = (q_s + r_s + ck_s) / 3
    else:
        score = (q_s + r_s) / 3
    return round(score, 2), ck_esp

def main():
    dias = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    hoje = date.today()

    with open(HIST_FILE, encoding="utf-8") as f:
        hist = json.load(f)

    # Encontra datas sem checklist dentro dos últimos N dias
    corte = str(hoje - timedelta(days=dias))
    datas_sem = defaultdict(list)
    for rec in hist:
        d = rec["data"]
        if d >= corte and not rec.get("tem_checklist"):
            datas_sem[d].append(rec)

    print(f"Datas a corrigir: {len(datas_sem)} ({sorted(datas_sem.keys())[0] if datas_sem else '-'} → {sorted(datas_sem.keys())[-1] if datas_sem else '-'})")

    cache_counts = {}
    for d in sorted(datas_sem.keys()):
        if d not in cache_counts:
            print(f"  Buscando {d}...", end=" ", flush=True)
            counts = buscar_counts(d)
            cache_counts[d] = counts or {}
            total = sum((counts or {}).values())
            print(f"{total} execuções")

        counts = cache_counts[d]
        for rec in datas_sem[d]:
            lid = rec["unidade_id"]
            ck_exec = counts.get(lid, 0)
            score, ck_esp = recalcular_score(rec, ck_exec)
            rec["checklist_executado"] = ck_exec
            rec["checklist_esperado"]  = ck_esp
            rec["tem_checklist"]       = ck_exec > 0
            rec["maturidade_score"]    = score

    with open(HIST_FILE, "w", encoding="utf-8") as f:
        json.dump(hist, f, ensure_ascii=False, indent=2)
    print(f"\nHistorico atualizado com {len(datas_sem)} datas.")

main()
