"""
Le todos os relatorios operacionais do Firestore (projeto quadro-cantucci)
colecoes: unidades_reports + mane_reports
Salva em RELATORIO_DADOS.json

Uso: py -3 relatorio_mapear_tudo.py
"""

import json
import urllib.request
from datetime import datetime

FIREBASE_API_KEY = "AIzaSyB_EOO59ePTfIchITlXCMaNOUPGMy7P2j0"
PROJECT_ID = "quadro-cantucci"

UNIT_NAMES = {
    "asa-sul": "Asa Sul",
    "asa-norte": "Asa Norte",
    "aguas-claras": "Aguas Claras",
    "superquadra": "Superquadra Norte",
    "koji": "Koji",
    "mane": "Mane",
}

def firestore_get(collection, page_token=None):
    url = (
        f"https://firestore.googleapis.com/v1/projects/{PROJECT_ID}"
        f"/databases/(default)/documents/{collection}"
        f"?key={FIREBASE_API_KEY}&pageSize=300"
    )
    if page_token:
        url += f"&pageToken={page_token}"
    with urllib.request.urlopen(url) as r:
        return json.loads(r.read())

def parse_value(v):
    if "stringValue" in v:   return v["stringValue"]
    if "integerValue" in v:  return int(v["integerValue"])
    if "doubleValue" in v:   return float(v["doubleValue"])
    if "booleanValue" in v:  return v["booleanValue"]
    if "nullValue" in v:     return None
    if "mapValue" in v:
        return {k: parse_value(vv) for k, vv in v["mapValue"].get("fields", {}).items()}
    if "arrayValue" in v:
        return [parse_value(i) for i in v["arrayValue"].get("values", [])]
    return str(v)

def parse_doc(doc):
    fields = doc.get("fields", {})
    return {k: parse_value(v) for k, v in fields.items()}

def fetch_all(collection):
    docs = []
    token = None
    while True:
        data = firestore_get(collection, token)
        for d in data.get("documents", []):
            parsed = parse_doc(d)
            parsed["_id"] = d["name"].split("/")[-1]
            docs.append(parsed)
        token = data.get("nextPageToken")
        if not token:
            break
    return docs

print("Buscando relatorios de unidades...")
unidades_reports = fetch_all("unidades_reports")
print(f"  {len(unidades_reports)} relatorios de unidades")

print("Buscando relatorios do Mane...")
mane_reports = fetch_all("mane_reports")
print(f"  {len(mane_reports)} relatorios do Mane")

# Estatisticas
todos = unidades_reports + mane_reports
por_unidade = {}
for r in todos:
    u = r.get("unit") or ("mane" if r in mane_reports else "?")
    if r in mane_reports:
        u = "mane"
    nome = UNIT_NAMES.get(u, u)
    por_unidade[nome] = por_unidade.get(nome, 0) + 1

notas = [float(r["notaTurno"]) for r in unidades_reports if r.get("notaTurno") is not None]
nota_media = round(sum(notas) / len(notas), 1) if notas else None

# Problemas mais frequentes (unidades padrao)
problemas = {
    "atraso_cozinha": sum(1 for r in unidades_reports if r.get("temAtraso")),
    "erro_qualidade": sum(1 for r in unidades_reports if r.get("temErroQualidade")),
    "reclamacao_atendimento": sum(1 for r in unidades_reports if r.get("temReclamacaoAtendimento")),
    "ruptura_salao": sum(1 for r in unidades_reports if r.get("temReclamacaoRuptura")),
    "delivery_atraso": sum(1 for r in unidades_reports if r.get("deliveryAtraso")),
    "delivery_erro": sum(1 for r in unidades_reports if r.get("deliveryErroDespacho")),
    "equipamento_quebrado": sum(1 for r in unidades_reports if r.get("equipamentoQuebrado")),
    "problema_sistema": sum(1 for r in unidades_reports if r.get("problemaSistema")),
}

resultado = {
    "gerado_em": datetime.now().isoformat(),
    "total_relatorios": len(todos),
    "unidades_reports": len(unidades_reports),
    "mane_reports": len(mane_reports),
    "por_unidade": por_unidade,
    "nota_media_turno": nota_media,
    "problemas_frequentes": problemas,
    "relatorios_unidades": unidades_reports,
    "relatorios_mane": mane_reports,
}

with open("RELATORIO_DADOS.json", "w", encoding="utf-8") as f:
    json.dump(resultado, f, ensure_ascii=False, indent=2)

print("\nOK! RELATORIO_DADOS.json salvo!")
print(f"   Total: {len(todos)} relatorios")
for u, n in sorted(por_unidade.items()):
    print(f"   {u}: {n}")
if nota_media:
    print(f"   Nota media de turno: {nota_media}/10")
