"""
Lê todos os quadros operacionais do Firestore (projeto quadro-cantucci)
via REST API e salva em QUADRO_DADOS.json.

Uso: py -3 quadro_mapear_tudo.py
"""

import json
import urllib.request
import os
import sys
from datetime import datetime, date, timedelta

FIREBASE_API_KEY = "AIzaSyB_EOO59ePTfIchITlXCMaNOUPGMy7P2j0"
PROJECT_ID = "quadro-cantucci"
DIR = os.path.dirname(os.path.abspath(__file__))
SAIDA = os.path.join(DIR, "QUADRO_DADOS.json")

# Busca apenas os últimos N dias para evitar rate limit do Firestore
DIAS_RECENTES = int(sys.argv[1]) if len(sys.argv) > 1 else 5
DATA_CORTE = str(date.today() - timedelta(days=DIAS_RECENTES))

def firestore_query(data_inicio):
    """Busca documentos da coleção 'quadros' com data >= data_inicio via structured query."""
    url = (
        f"https://firestore.googleapis.com/v1/projects/{PROJECT_ID}"
        f"/databases/(default)/documents:runQuery?key={FIREBASE_API_KEY}"
    )
    body = json.dumps({
        "structuredQuery": {
            "from": [{"collectionId": "quadros"}],
            "where": {
                "fieldFilter": {
                    "field": {"fieldPath": "data"},
                    "op": "GREATER_THAN_OR_EQUAL",
                    "value": {"stringValue": data_inicio}
                }
            },
            "orderBy": [{"field": {"fieldPath": "data"}, "direction": "ASCENDING"}]
        }
    }).encode("utf-8")
    req = urllib.request.Request(url, data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())

def firestore_get(collection, page_token=None):
    url = (
        f"https://firestore.googleapis.com/v1/projects/{PROJECT_ID}"
        f"/databases/(default)/documents/{collection}"
        f"?key={FIREBASE_API_KEY}&pageSize=10"
    )
    if page_token:
        url += f"&pageToken={page_token}"
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req) as r:
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

# Carrega histórico existente
quadros_existentes = {}
if os.path.exists(SAIDA):
    with open(SAIDA, encoding="utf-8") as f:
        old = json.load(f)
    for q in (old if isinstance(old, list) else old.get("quadros", [])):
        quadros_existentes[q.get("_id", q.get("data","") + q.get("unidade",""))] = q

print(f"Buscando quadros recentes (>= {DATA_CORTE})...")
rows = firestore_query(DATA_CORTE)
novos = 0
for row in rows:
    doc = row.get("document")
    if not doc:
        continue
    parsed = parse_doc(doc)
    parsed["_id"] = doc["name"].split("/")[-1]
    chave = parsed["_id"]
    if chave not in quadros_existentes:
        novos += 1
    quadros_existentes[chave] = parsed

quadros = list(quadros_existentes.values())
print(f"  {len(quadros)} quadros no total ({novos} novos)")

print("Buscando equipe...")
try:
    eq_data = firestore_get("equipe")
    equipe_docs = [parse_doc(d) for d in eq_data.get("documents", [])]
    equipe = equipe_docs[0] if equipe_docs else {}
    print(f"  equipe OK")
except Exception as e:
    equipe = {}
    print(f"  equipe ERRO: {e}")

# Estatísticas rápidas
unidades = {}
for q in quadros:
    u = q.get("unidade", "?")
    unidades[u] = unidades.get(u, 0) + 1

freelas_total = sum(q.get("freelas", 0) or 0 for q in quadros)
alertas_escala = sum(1 for q in quadros if q.get("alerta_escala"))
alertas_rupturas = sum(1 for q in quadros if q.get("alerta_rupturas"))

resultado = {
    "gerado_em": datetime.now().isoformat(),
    "total_quadros": len(quadros),
    "unidades": unidades,
    "freelas_total": freelas_total,
    "alertas_escala": alertas_escala,
    "alertas_rupturas": alertas_rupturas,
    "equipe": equipe,
    "quadros": quadros
}

with open("QUADRO_DADOS.json", "w", encoding="utf-8") as f:
    json.dump(resultado, f, ensure_ascii=False, indent=2)

print("\nOK! QUADRO_DADOS.json salvo com sucesso!")
print(f"   Total: {len(quadros)} quadros")
print(f"   Unidades: {', '.join(unidades.keys())}")
print(f"   Freelas: {freelas_total}")
print(f"   Alertas escala: {alertas_escala} | Rupturas: {alertas_rupturas}")
