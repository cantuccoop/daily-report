"""
Consulta checklists aplicados por dia no ChecklistFacil.
Faz login automatico com email+senha (sem depender de cookies salvos).
Uso: python checklistfacil_consultar.py [DD/MM/AAAA]
"""
import sys, json, os, re
from datetime import datetime
from playwright.sync_api import sync_playwright

EMAIL = os.environ.get('CHECKLIST_EMAIL', 'operacoes@cantucci.com.br')
SENHA = os.environ.get('CHECKLIST_SENHA', 'Cantucci123!')
DIR   = os.path.dirname(os.path.abspath(__file__))

def buscar_checklists(data_br=None):
    if not data_br:
        data_br = datetime.today().strftime('%d/%m/%Y')

    execucoes = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
            ]
        )
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
            viewport={'width': 1280, 'height': 800},
            locale='pt-BR',
        )
        # Oculta webdriver flag
        context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        page = context.new_page()

        # ── Login ──────────────────────────────────────────────────────────────
        print('  ChecklistFacil: fazendo login...')
        page.goto('https://spa.checklistfacil.com.br/login?lang=pt-br', wait_until='networkidle', timeout=30000)

        # Etapa 1: preenche email e clica Continuar
        page.wait_for_selector('input[name="user-name"]', timeout=15000)
        page.fill('input[name="user-name"]', EMAIL)
        page.wait_for_timeout(600)
        # Clica via JS para evitar overlay interceptando
        page.evaluate("document.querySelector('button[type=\"submit\"]').click()")
        page.wait_for_timeout(2000)

        # Etapa 2: preenche senha via JS e clica Entrar
        page.wait_for_selector('input[name="user-password"]', timeout=15000)
        page.evaluate(f"""
            const inp = document.querySelector('input[name="user-password"]');
            if (inp) {{
                inp.removeAttribute('disabled');
                const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                setter.call(inp, '{SENHA}');
                inp.dispatchEvent(new Event('input', {{bubbles: true}}));
                inp.dispatchEvent(new Event('change', {{bubbles: true}}));
            }}
        """)
        page.wait_for_timeout(600)
        page.evaluate("document.querySelector('button[type=\"submit\"]').click()")
        page.wait_for_timeout(3000)

        # Aguarda sair do login (até 20s)
        try:
            page.wait_for_url(re.compile(r'(?!.*login)'), timeout=20000)
        except Exception:
            # verifica se está logado mesmo sem redirect
            pass

        if 'login' in page.url:
            print('  ChecklistFacil: login falhou (reCAPTCHA ou credencial)')
            browser.close()
            return []

        print(f'  ChecklistFacil: logado — {page.url}')

        # ── Scraping de execuções ──────────────────────────────────────────────
        pagina = 1
        while True:
            url = (f'https://app.checklistfacil.com.br/evaluations'
                   f'?status[]=completed&period=start'
                   f'&start_date={data_br}&end_date={data_br}'
                   f'&units[]=all&page={pagina}')
            page.goto(url, wait_until='networkidle', timeout=20000)

            # Redireccionou para login = sessão não transferiu
            if 'login' in page.url:
                print('  ChecklistFacil: sessao nao transferiu para app')
                break

            html = page.content()
            tbody = re.search(r'<tbody[^>]*>(.*?)</tbody>', html, re.DOTALL)
            if not tbody:
                break

            trs = re.findall(r'<tr[^>]*>(.*?)</tr>', tbody.group(1), re.DOTALL)
            if not trs:
                break

            novos = 0
            for tr in trs:
                tds = re.findall(r'<td[^>]*>(.*?)</td>', tr, re.DOTALL)
                textos = [re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', td)).strip() for td in tds]
                if len(textos) >= 6:
                    unidade   = textos[3] if len(textos) > 3 else ''
                    checklist = textos[4] if len(textos) > 4 else ''
                    data_hora = textos[5] if len(textos) > 5 else ''
                    resp      = textos[6] if len(textos) > 6 else ''
                    nota      = textos[7].split()[0] if len(textos) > 7 else ''
                    if unidade and checklist and 'Excluir' not in unidade:
                        execucoes.append({
                            'unidade': unidade, 'checklist': checklist,
                            'data_hora': data_hora, 'responsavel': resp, 'nota': nota,
                        })
                        novos += 1

            print(f'  Página {pagina}: {novos} registros')
            if len(trs) < 20:
                break
            pagina += 1

        browser.close()

    return execucoes


def main():
    data = sys.argv[1] if len(sys.argv) > 1 else datetime.today().strftime('%d/%m/%Y')
    print(f'\n  Buscando checklists de {data}...')

    execucoes = buscar_checklists(data)

    resultado = {'data': data, 'total': len(execucoes), 'execucoes': execucoes}
    out = os.path.join(DIR, 'checklistfacil_resultado.json')
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(resultado, f, ensure_ascii=False, indent=2)

    print(f'  Total: {len(execucoes)} execuções salvas')

main()
