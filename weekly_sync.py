"""
weekly_sync.py — Agrega os dados da semana (segunda a domingo) e salva em WEEKLY_CACHE.json

Faturamento, meta, maturidade, quadro operacional, relatório de turno e checklist
vêm do HISTORICO_DIARIO.json (já coletado dia a dia pelo daily_sync.py).
Reputação (Falaê) é buscada direto na API para a semana inteira.
CMC da semana e CMV do mês corrente vêm do CMC_CMV_DADOS.json, gerado pelo
cmc_cmv_mapear.py (painel Grupo 3V) — precisa rodar antes deste script.
Delivery, descontos, upsell, alcoólica, TMA e projeção do mês vêm do
CANTUCCI_OS_SEMANAL.json, gerado pelo cantucci_os_semanal.py (API Cantucci OS)
— também precisa rodar antes.

Uso: py -3 weekly_sync.py [YYYY-MM-DD]   (qualquer data dentro da semana alvo; sem argumento = semana passada)
"""
import sys, json, os
from datetime import date, timedelta
from concurrent.futures import ThreadPoolExecutor
import requests

_E = os.environ.get
FALAE_EMAIL = _E('FALAE_EMAIL', 'operacoes@cantucci.com.br')
FALAE_SENHA = _E('FALAE_SENHA', 'Gestorop2026!')

sys.stdout.reconfigure(encoding='utf-8')

DIR = os.path.dirname(os.path.abspath(__file__))


def semana_de(data_str):
    dt = date.fromisoformat(data_str)
    segunda = dt - timedelta(days=dt.weekday())
    return segunda, segunda + timedelta(days=6)


if len(sys.argv) > 1:
    REF = sys.argv[1]
else:
    hoje = date.today()
    REF = str(hoje - timedelta(days=hoje.weekday() + 1))  # domingo anterior

SEGUNDA, DOMINGO = semana_de(REF)
SEGUNDA_ISO, DOMINGO_ISO = SEGUNDA.isoformat(), DOMINGO.isoformat()

LOJAS = [
    ('cantucci_an', 'Cantucci Asa Norte'),
    ('cantucci_as', 'Cantucci Asa Sul'),
    ('cantucci_ac', 'Cantucci Águas Claras'),
    ('superquadra', 'Superquadra Norte'),
    ('mane', 'Mané'),
    ('koji', 'Koji'),
]

# Para AN, AS, AC: média de 3 marcas (Cantucci + Grano & Oliva + Inforno)
FALAE_COMPANIES = {
    'cantucci_an': ['7657a307-a357-444d-8673-8589a6d6da8f',
                    '44eb5591-49a6-4a0d-a20e-409a1e423016',
                    '420b2d11-c98a-4351-97a0-0e8dcf8981c8'],
    'cantucci_as': ['a579aa4e-8937-4454-85ac-0b93fbeec71b',
                    'cabe5170-21f6-4ec8-a23b-71ad3daa64a3',
                    'c976aa3a-e8a6-494d-8795-bfe798805b68'],
    'cantucci_ac': ['665f8187-635c-4d83-819d-1b179ce6def5',
                    '89c6aab7-9c15-4a76-a830-c64b75c4f4a8',
                    'b969d6d3-44ac-47b0-9693-43138132c28c'],
    'koji': ['3faa8821-157d-45c6-9505-e9942e9ba084'],
    'superquadra': ['7345ef8f-6ed8-4d43-a17a-4d4a2059e680'],
}

cache = {
    'semana_inicio': SEGUNDA_ISO,
    'semana_fim': DOMINGO_ISO,
    'gerado_em': str(date.today()),
    'mes_referencia_cmv': None,
    'mes_referencia_projecao': None,
    'lojas': {},
    'erros': [],
}
for lid, _ in LOJAS:
    cache['lojas'][lid] = {
        'dias': 0, 'faturamento': None, 'meta': None,
        'maturidade_media': None,
        'quadro_turnos': 0, 'relatorio_turnos': 0,
        'checklist_executado': 0, 'checklist_esperado': 0,
        'google': None, 'ifood': None, 'reviews_semana': None,
        'detratores_google': None, 'detratores_ifood': None,
        'cmc_semana_pct': None, 'cmv_mes_pct': None, 'cmv_mes_meta_pct': None,
        'pct_delivery': None, 'ticket_medio_geral': None,
        'descontos_qtd': None, 'descontos_valor': None,
        'cancelamentos_qtd': None, 'cancelamentos_valor': None,
        'pct_upsell': None, 'fat_upsell': None,
        'pct_alcoolica': None, 'fat_alcoolica': None,
        'tma_cozinha_min': None, 'pct_tma_acima_20': None,
        'projecao_mes': None, 'meta_mes': None, 'projecao_pct_meta': None,
    }


def log(msg):
    print(f'  {msg}')


# ─── 1. Histórico diário já coletado ──────────────────────────────────────────
def agregar_historico():
    log('Agregando histórico diário...')
    hist_path = os.path.join(DIR, 'HISTORICO_DIARIO.json')
    if not os.path.exists(hist_path):
        cache['erros'].append('historico: HISTORICO_DIARIO.json não encontrado')
        return
    with open(hist_path, encoding='utf-8') as f:
        historico = json.load(f)
    regs = [h for h in historico if SEGUNDA_ISO <= h['data'] <= DOMINGO_ISO]
    for lid, _ in LOJAS:
        u_regs = [h for h in regs if h['unidade_id'] == lid]
        if not u_regs:
            continue
        loja = cache['lojas'][lid]
        loja['dias'] = len(u_regs)
        loja['faturamento'] = round(sum(h.get('faturamento') or 0 for h in u_regs), 2) or None
        loja['meta'] = round(sum(h.get('meta') or 0 for h in u_regs), 2) or None
        scores = [h['maturidade_score'] for h in u_regs if h.get('maturidade_score') is not None]
        loja['maturidade_media'] = round(sum(scores) / len(scores), 1) if scores else None
        loja['quadro_turnos'] = sum(h.get('quadro_turnos') or 0 for h in u_regs)
        loja['relatorio_turnos'] = sum(h.get('relatorio_turnos') or 0 for h in u_regs)
        loja['checklist_executado'] = sum(h.get('checklist_executado') or 0 for h in u_regs)
        loja['checklist_esperado'] = sum(h.get('checklist_esperado') or 0 for h in u_regs)
    log(f'Histórico OK — {len(regs)} registros na semana')


# ─── 2. CMC/CMV (painel Grupo 3V) — coletado pelo cmc_cmv_mapear.py ──────────
def carregar_cmc_cmv():
    log('Carregando CMC/CMV...')
    path = os.path.join(DIR, 'CMC_CMV_DADOS.json')
    if not os.path.exists(path):
        cache['erros'].append('cmc_cmv: CMC_CMV_DADOS.json não encontrado — rode cmc_cmv_mapear.py')
        return
    with open(path, encoding='utf-8') as f:
        dados = json.load(f)
    if dados.get('semana_inicio') != SEGUNDA_ISO:
        cache['erros'].append(f'cmc_cmv: cache é da semana de {dados.get("semana_inicio")}')
        return
    cache['mes_referencia_cmv'] = dados.get('mes_referencia')
    ok = 0
    for lid, u in dados.get('unidades', {}).items():
        if lid not in cache['lojas'] or u.get('erro'):
            continue
        cache['lojas'][lid]['cmc_semana_pct'] = u.get('cmc_semana_pct')
        cache['lojas'][lid]['cmv_mes_pct'] = u.get('cmv_mes_pct')
        cache['lojas'][lid]['cmv_mes_meta_pct'] = u.get('cmv_mes_meta_pct')
        if u.get('cmc_semana_pct') is not None:
            ok += 1
    log(f'CMC/CMV OK — {ok} unidades')


# ─── 3. Cantucci OS (delivery/descontos/upsell/alcoólica/TMA/projeção) ───────
def carregar_cantucci_os():
    log('Carregando Cantucci OS...')
    path = os.path.join(DIR, 'CANTUCCI_OS_SEMANAL.json')
    if not os.path.exists(path):
        cache['erros'].append('cantucci_os: CANTUCCI_OS_SEMANAL.json não encontrado — rode cantucci_os_semanal.py')
        return
    with open(path, encoding='utf-8') as f:
        dados = json.load(f)
    if dados.get('semana_inicio') != SEGUNDA_ISO:
        cache['erros'].append(f'cantucci_os: cache é da semana de {dados.get("semana_inicio")}')
        return
    cache['mes_referencia_projecao'] = dados.get('mes_referencia_projecao')
    ok = 0
    campos = ['pct_delivery', 'ticket_medio_geral', 'descontos_qtd', 'descontos_valor',
              'cancelamentos_qtd', 'cancelamentos_valor',
              'pct_upsell', 'fat_upsell', 'pct_alcoolica', 'fat_alcoolica',
              'tma_cozinha_min', 'pct_tma_acima_20', 'projecao_mes', 'meta_mes', 'projecao_pct_meta']
    for lid, u in dados.get('lojas', {}).items():
        if lid not in cache['lojas']:
            continue
        for campo in campos:
            cache['lojas'][lid][campo] = u.get(campo)
        if u.get('pct_delivery') is not None:
            ok += 1
    log(f'Cantucci OS OK — {ok} unidades')


# ─── 4. Falaê — reputação média da semana ────────────────────────────────────
def sync_falae():
    log('Falaê (semana)...')
    try:
        r = requests.post('https://api-b2s.experienciab2s.com/sessions',
                           json={'email': FALAE_EMAIL, 'password': FALAE_SENHA}, timeout=10)
        tok = r.json()['token']
        user_cid = r.json()['user']['company_id']
        h = {'Authorization': f'Bearer {tok}', 'company_id': user_cid}

        def fetch_reviews_baixas(cid, plat):
            endpoint = {
                'google': 'https://api-b2s.experienciab2s.com/integrations/reviewsGoogle/pagination',
                'ifood': 'https://api-b2s.experienciab2s.com/integrations/ifood/pagination',
            }[plat]
            campo_nota = 'grade'
            campo_comment = 'comment'
            campo_cliente = {'google': 'client_name', 'ifood': 'customer'}[plat]
            try:
                rr = requests.get(endpoint,
                                   params={'companies_id': cid, 'date_start': SEGUNDA_ISO, 'date_end': DOMINGO_ISO,
                                           'offset': 1, 'limit': 100,
                                           'order_column': 'comment_date', 'order_type': 'DESC'},
                                   headers={**h, 'company_id': cid}, timeout=10)
                if not rr.ok:
                    return []
                j = rr.json()
                items = j.get('reviews', []) if isinstance(j, dict) else j
                if not isinstance(items, list):
                    items = []
                baixas = []
                for it in items:
                    nota = it.get(campo_nota) or 0
                    if nota <= 2:
                        cliente = it.get(campo_cliente) or 'Anônimo'
                        texto = (it.get(campo_comment) or '').strip()
                        baixas.append({'nota': nota, 'cliente': cliente, 'texto': texto})
                return baixas
            except Exception:
                return []

        def fetch_rep(lid):
            cids = FALAE_COMPANIES.get(lid, [])
            if not cids:
                return lid, [], {}
            reps, baixas_textos = [], {'google': [], 'ifood': []}
            for cid in cids:
                rr = requests.get('https://api-b2s.experienciab2s.com/dashboard/reputation',
                                   params={'companies_id': cid, 'date_start': SEGUNDA_ISO, 'date_end': DOMINGO_ISO},
                                   headers={**h, 'company_id': cid}, timeout=10)
                if rr.ok:
                    rj = rr.json()
                    reps.append(rj)
                    for plat in ['google', 'ifood']:
                        bxs = ((rj.get(plat, {}).get('summary', {}).get('oneStar') or 0) +
                               (rj.get(plat, {}).get('summary', {}).get('twoStars') or 0))
                        if bxs:
                            baixas_textos[plat] += fetch_reviews_baixas(cid, plat)
            return lid, reps, baixas_textos

        with ThreadPoolExecutor(max_workers=4) as ex:
            results = list(ex.map(fetch_rep, list(FALAE_COMPANIES.keys())))

        def media_grade(reps, plat):
            grades = [r.get(plat, {}).get('summary', {}).get('grade')
                      for r in reps if r.get(plat, {}).get('summary', {}).get('grade')]
            totais = [r.get(plat, {}).get('summary', {}).get('total', 0) or 0 for r in reps]
            if not grades:
                return None, 0
            return round(sum(grades) / len(grades), 2), sum(totais)

        def qtd_detratores(reps, plat):
            return sum(((r.get(plat, {}).get('summary', {}).get('oneStar') or 0) +
                        (r.get(plat, {}).get('summary', {}).get('twoStars') or 0)) for r in reps)

        ok = 0
        for lid, reps, baixas_textos in results:
            if not reps:
                continue
            g_grade, g_total = media_grade(reps, 'google')
            i_grade, i_total = media_grade(reps, 'ifood')
            if g_grade or i_grade:
                cache['lojas'][lid]['google'] = {'grade': g_grade, 'total': g_total} if g_grade else None
                cache['lojas'][lid]['ifood'] = {'grade': i_grade, 'total': i_total} if i_grade else None
                cache['lojas'][lid]['detratores_google'] = qtd_detratores(reps, 'google')
                cache['lojas'][lid]['detratores_ifood'] = qtd_detratores(reps, 'ifood')
                reviews = {}
                for plat in ['google', 'ifood']:
                    bxs = baixas_textos.get(plat, [])
                    if bxs:
                        reviews[plat] = {'baixas': len(bxs), 'textos': bxs}
                cache['lojas'][lid]['reviews_semana'] = reviews or None
                ok += 1
        log(f'Falaê OK — {ok} unidades com reputação')
    except Exception as e:
        cache['erros'].append(f'falae: {e}')
        log(f'Falaê ERRO: {e}')


# ─── Main ─────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    print(f'\n🔄 SYNC SEMANAL — {SEGUNDA_ISO} a {DOMINGO_ISO}')
    print('─' * 40)

    agregar_historico()
    carregar_cmc_cmv()
    carregar_cantucci_os()
    sync_falae()

    cache_path = os.path.join(DIR, 'WEEKLY_CACHE.json')
    with open(cache_path, 'w', encoding='utf-8') as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)

    ok = sum(1 for l in cache['lojas'].values() if l.get('faturamento') is not None)
    print(f'\n✅ WEEKLY_CACHE.json salvo — {ok}/{len(LOJAS)} unidades com faturamento')
    if cache['erros']:
        print(f'⚠️  Erros: {", ".join(cache["erros"])}')
