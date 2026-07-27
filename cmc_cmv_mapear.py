"""
cmc_cmv_mapear.py — Login no painel CMC/CMV (Streamlit, Grupo 3V) e extrai por unidade:
  - CMC% da semana (tabela "Faturamento vs Compras por Semana")
  - CMV% do mês corrente (painel "Indicadores", único CMV que o painel calcula — não existe CMV semanal ali)

Uso: py -3 cmc_cmv_mapear.py [YYYY-MM-DD]   (data dentro da semana alvo; sem argumento = semana passada)
Dependências: pip install playwright
              playwright install chromium
"""
import sys, os, json, re, time
from datetime import date, timedelta
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding='utf-8')

URL = "https://anacecilia896cmc-grupo3v.streamlit.app/"
SENHA = os.environ.get('CMC_SENHA', 'CMV123')
DIR = os.path.dirname(os.path.abspath(__file__))

UNIDADES = [
    ('cantucci_an', 'Asa Norte'),
    ('cantucci_as', 'Asa Sul'),
    ('cantucci_ac', 'Aguas Claras'),
    ('superquadra', 'SPQ Norte'),
    ('mane', 'Mane'),
    ('koji', 'Koji'),
]

SEMANA_ROW_RE = re.compile(
    r'S\d+(\d{2}/\d{2})\s*–\s*(\d{2}/\d{2})CMC\s+([\d.,]+)%Faturamento\s*R\$\s*([\d,]+)'
    r'.*?Compras realizadas\s*R\$\s*([\d,]+)', re.DOTALL)
CMV_MES_RE = re.compile(r'CMV Realizado\s+([\d.,]+)%\s+Meta:\s*Meta:\s*([\d.,]+)%')
MES_REF_RE = re.compile(r'Indicadores — .*? · (\w+ / \d{4})')


def semana_de(data_str):
    dt = date.fromisoformat(data_str)
    segunda = dt - timedelta(days=dt.weekday())
    return segunda, segunda + timedelta(days=6)


if len(sys.argv) > 1:
    REF = sys.argv[1]
else:
    hoje = date.today()
    REF = str(hoje - timedelta(days=hoje.weekday() + 1))

SEGUNDA, DOMINGO = semana_de(REF)
SEGUNDA_LABEL = SEGUNDA.strftime('%d/%m')


def log(msg):
    print(f'  {msg}')


def get_full_text(frame, retries=3):
    for attempt in range(retries):
        try:
            md = frame.locator('[data-testid="stMarkdownContainer"]')
            n = md.count()
            return "\n".join(md.nth(i).inner_text(timeout=5000) for i in range(n))
        except Exception:
            if attempt == retries - 1:
                raise
            time.sleep(1.5)


def get_indicadores_heading(frame):
    loc = frame.locator('[data-testid="stMarkdownContainer"]', has_text='Indicadores —')
    if loc.count() == 0:
        return None
    try:
        return loc.first.inner_text(timeout=5000)
    except Exception:
        return None


def select_unidade(frame, page, label):
    boxes = frame.locator('[data-testid="stSelectbox"]')
    for i in range(boxes.count()):
        box = boxes.nth(i)
        if box.locator('label').inner_text() == 'Unidade':
            before = get_indicadores_heading(frame)
            box.locator('input').click()
            page.wait_for_timeout(500)
            frame.locator(f'[role="option"]:has-text("{label}")').first.click()
            # espera o cabeçalho "Indicadores — <unidade>" mudar, confirmando a troca
            for _ in range(20):
                page.wait_for_timeout(750)
                after = get_indicadores_heading(frame)
                if after and after != before:
                    break
            return True
    return False


def parse_num(txt):
    return float(txt.replace(',', ''))


resultado = {
    'semana_inicio': SEGUNDA.isoformat(),
    'semana_fim': DOMINGO.isoformat(),
    'mes_referencia': None,
    'gerado_em': str(date.today()),
    'unidades': {},
}

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    log('Login no painel CMC/CMV...')
    page.goto(URL, wait_until='load', timeout=60000)
    time.sleep(4)
    frame = page.frame_locator('iframe[title="streamlitApp"]')
    frame.locator('input[type="password"]').fill(SENHA)
    frame.locator('input[type="password"]').press('Enter')
    page.wait_for_timeout(8000)

    for lid, unidade_label in UNIDADES:
        log(f'{unidade_label}...')
        try:
            if not select_unidade(frame, page, unidade_label):
                raise Exception('seletor de unidade não encontrado')
            page.wait_for_timeout(3000)
            full = get_full_text(frame)

            semana_match = None
            for m in SEMANA_ROW_RE.finditer(full):
                if m.group(1) == SEGUNDA_LABEL:
                    semana_match = m
                    break

            cmv_match = CMV_MES_RE.search(full)
            mes_match = MES_REF_RE.search(full)
            if mes_match and not resultado['mes_referencia']:
                resultado['mes_referencia'] = mes_match.group(1)

            resultado['unidades'][lid] = {
                'unidade': unidade_label,
                'cmc_semana_pct': float(semana_match.group(3)) if semana_match else None,
                'faturamento_semana': parse_num(semana_match.group(4)) if semana_match else None,
                'compras_semana': parse_num(semana_match.group(5)) if semana_match else None,
                'cmv_mes_pct': float(cmv_match.group(1).replace(',', '.')) if cmv_match else None,
                'cmv_mes_meta_pct': float(cmv_match.group(2).replace(',', '.')) if cmv_match else None,
            }
        except Exception as e:
            resultado['unidades'][lid] = {'unidade': unidade_label, 'erro': str(e)}
            log(f'{unidade_label} ERRO: {e}')

    browser.close()

out_path = os.path.join(DIR, 'CMC_CMV_DADOS.json')
with open(out_path, 'w', encoding='utf-8') as f:
    json.dump(resultado, f, ensure_ascii=False, indent=2)

ok = sum(1 for u in resultado['unidades'].values() if u.get('cmc_semana_pct') is not None)
print(f'\n✅ CMC_CMV_DADOS.json salvo — {ok}/{len(UNIDADES)} unidades com CMC da semana')
