"""
Faz login no dashboard3v.vercel.app, acessa todas as unidades/rotas
e salva os dados em DASHBOARD3V_DADOS.json.

Uso: py -3 dashboard3v_mapear.py
Dependencias: pip install playwright beautifulsoup4
              playwright install chromium
"""

import json, os, re
from datetime import datetime
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

EMAIL = os.environ.get('DASHBOARD3V_EMAIL', 'operacoes@cantucci.com.br')
SENHA = os.environ.get('DASHBOARD3V_SENHA', 'jU20263v')
BASE_URL = "https://dashboard3v.vercel.app"

UNITS = {
    "Aguas Claras":      "f50e16c5-800f-41a7-9280-bb8a65a06578",
    "Asa Norte":         "b9efac1e-d04f-41b7-bacc-f8759ab4da6b",
    "Asa Sul":           "9b72f471-4f97-4967-bed4-b5a2277bc7d4",
    "Superquadra Norte": "c8a89042-1c82-4659-b650-4dda828ba6b5",
    "Koji":              "4a45215c-c38b-418d-80a6-4167efb7559a",
    "Mane":              "3cbb2efb-506f-4d20-8a93-82782cc47a9f",
}

MES_ATUAL = datetime.now().strftime("%Y-%m-01")


def login(page):
    print("Fazendo login...")
    page.goto(f"{BASE_URL}/login", wait_until="networkidle")
    page.fill('input[name="email"]', EMAIL)
    page.fill('input[name="password"]', SENHA)
    page.click('button[type="submit"]')
    page.wait_for_url(f"{BASE_URL}/dashboard**", timeout=20000)
    print("Login OK")


def get_html(page, url):
    page.goto(url, wait_until="networkidle", timeout=30000)
    return page.content()


def parse_dashboard(html, unit_name):
    soup = BeautifulSoup(html, "html.parser")
    result = {"unidade": unit_name, "categorias": [], "totais": {}}

    # Tenta extrair valores do HTML renderizado
    text = soup.get_text(" ", strip=True)

    # Acumulado e meta (padrão: "R$ X.XXX,XX")
    valores = re.findall(r"R\$\s*([\d.,]+)", text)
    percentuais = re.findall(r"([\d,]+)%", text)

    # Extrai linhas de tabela se existirem
    rows = soup.find_all("tr")
    for row in rows:
        cells = [td.get_text(strip=True) for td in row.find_all(["td", "th"])]
        if len(cells) >= 3:
            result["categorias"].append(cells)

    # Tenta capturar texto de acumulado e meta
    acumulado_match = re.search(r"Acumulado[^R]*R\$\s*([\d.,]+)", text)
    meta_match = re.search(r"Meta[^R]*R\$\s*([\d.,]+)", text)
    pct_match = re.search(r"([\d,]+)%\s*(?:da meta|atingido)", text, re.IGNORECASE)

    if acumulado_match:
        result["totais"]["acumulado"] = acumulado_match.group(1)
    if meta_match:
        result["totais"]["meta"] = meta_match.group(1)
    if pct_match:
        result["totais"]["percentual"] = pct_match.group(1)

    result["_html_len"] = len(html)
    result["_raw_text"] = text[:3000]
    return result


def parse_comparativo(html):
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(" ", strip=True)
    rows = soup.find_all("tr")
    tabela = []
    for row in rows:
        cells = [td.get_text(strip=True) for td in row.find_all(["td", "th"])]
        if cells:
            tabela.append(cells)
    return {"tabela": tabela, "_raw_text": text[:4000]}


with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context()
    page = context.new_page()

    login(page)

    dados = {
        "gerado_em": datetime.now().isoformat(),
        "mes": MES_ATUAL,
        "units": UNITS,
        "dashboard": {},
        "comparativo": None,
        "historico": {},
    }

    # Dashboard por unidade
    for nome, uid in UNITS.items():
        print(f"  Dashboard: {nome}...")
        url = f"{BASE_URL}/dashboard?unit={uid}&month={MES_ATUAL}&view=mes"
        try:
            html = get_html(page, url)
            dados["dashboard"][nome] = parse_dashboard(html, nome)
        except Exception as e:
            dados["dashboard"][nome] = {"erro": str(e)}

    # Comparativo (qualquer unidade como ponto de entrada)
    print("  Comparativo...")
    uid_ref = UNITS["Asa Norte"]
    try:
        html = get_html(page, f"{BASE_URL}/dashboard/comparativo?unit={uid_ref}&month={MES_ATUAL}")
        dados["comparativo"] = parse_comparativo(html)
    except Exception as e:
        dados["comparativo"] = {"erro": str(e)}

    # Historico por unidade
    for nome, uid in UNITS.items():
        print(f"  Historico: {nome}...")
        try:
            html = get_html(page, f"{BASE_URL}/dashboard/historico?unit={uid}")
            soup = BeautifulSoup(html, "html.parser")
            dados["historico"][nome] = {"_raw_text": soup.get_text(" ", strip=True)[:2000]}
        except Exception as e:
            dados["historico"][nome] = {"erro": str(e)}

    browser.close()

with open("DASHBOARD3V_DADOS.json", "w", encoding="utf-8") as f:
    json.dump(dados, f, ensure_ascii=False, indent=2)

print("\nOK! DASHBOARD3V_DADOS.json salvo!")
print(f"   Unidades: {', '.join(UNITS.keys())}")
print(f"   Mes: {MES_ATUAL}")
