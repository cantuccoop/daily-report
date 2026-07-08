"""
daily_sync.py — Coleta todos os dados do dia e salva em DAILY_CACHE.json
Roda às 23h via Task Scheduler. Robusto: erro em uma fonte não cancela as demais.

Uso: py -3 daily_sync.py [YYYY-MM-DD]   (sem argumento = hoje)
"""
import sys, json, os, subprocess, re
from datetime import date, timedelta
from concurrent.futures import ThreadPoolExecutor
import requests

# Credenciais — lê de env vars (GitHub Actions) ou usa fallback local
_E = os.environ.get
CANTUCCI_OS_USER  = _E('CANTUCCI_OS_USER',  'julhyana')
CANTUCCI_OS_PASS  = _E('CANTUCCI_OS_PASS',  'julhyana90!')
FALAE_EMAIL       = _E('FALAE_EMAIL',        'operacoes@cantucci.com.br')
FALAE_SENHA       = _E('FALAE_SENHA',        'Gestorop2026!')
DASHBOARD3V_EMAIL = _E('DASHBOARD3V_EMAIL',  'operacoes@cantucci.com.br')
DASHBOARD3V_SENHA = _E('DASHBOARD3V_SENHA',  'jU20263v')

sys.stdout.reconfigure(encoding='utf-8')

DATA = sys.argv[1] if len(sys.argv) > 1 else str(date.today() - timedelta(days=1))
DATA_DT = date.fromisoformat(DATA)
SEMANA_INICIO = str(DATA_DT - timedelta(days=DATA_DT.weekday()))
DIR = os.path.dirname(os.path.abspath(__file__))


# (lid, api_id, label)  — api_id é o que vai para a Cantucci OS API
LOJAS_OS = [
    ('cantucci_an',     'cantucci_an',      'Cantucci Asa Norte'),
    ('cantucci_as',     'cantucci_as',      'Cantucci Asa Sul'),
    ('cantucci_ac',     'cantucci_ac',      'Cantucci Águas Claras'),
    ('superquadra',     'superquadra',      'Superquadra Norte'),
    ('mane',            'Superquadra Mané', 'Mané'),
    ('mane',            'Véi Chico Mané',   'Mané'),
    ('koji',            'koji',             'Koji'),
]
# Para AN, AS, AC: média de 3 marcas (Cantucci + Grano & Oliva + Inforno)
FALAE_COMPANIES = {
    'cantucci_an': ['7657a307-a357-444d-8673-8589a6d6da8f',   # Cantucci AN
                    '44eb5591-49a6-4a0d-a20e-409a1e423016',   # Grano & Oliva AN
                    '420b2d11-c98a-4351-97a0-0e8dcf8981c8'],  # Inforno AN
    'cantucci_as': ['a579aa4e-8937-4454-85ac-0b93fbeec71b',   # Cantucci AS
                    'cabe5170-21f6-4ec8-a23b-71ad3daa64a3',   # Grano & Oliva AS
                    'c976aa3a-e8a6-494d-8795-bfe798805b68'],  # Inforno AS
    'cantucci_ac': ['665f8187-635c-4d83-819d-1b179ce6def5',   # Cantucci AC
                    '89c6aab7-9c15-4a76-a830-c64b75c4f4a8',   # Grano & Oliva AC
                    'b969d6d3-44ac-47b0-9693-43138132c28c'],  # Inforno AC
    'koji':        ['3faa8821-157d-45c6-9505-e9942e9ba084'],
    'superquadra': ['7345ef8f-6ed8-4d43-a17a-4d4a2059e680'],  # Superquadra Bar
}
# Mapeamento loja_id -> slug usado no RELATORIO_DADOS.json
LOJA_SLUG = {
    'cantucci_an':     'asa-norte',
    'cantucci_as':     'asa-sul',
    'cantucci_ac':     'aguas-claras',
    'superquadra':     'superquadra',
    'mane':            'mane',
    'koji':            'koji',
}
# Mapeamento loja_id -> chave no DASHBOARD3V_DADOS.json
LOJA_3V = {
    'cantucci_an':     'Asa Norte',
    'cantucci_as':     'Asa Sul',
    'cantucci_ac':     'Aguas Claras',
    'superquadra':     'Superquadra Norte',
    'mane':            'Mane',
    'koji':            'Koji',
}
VMARKET_FILIAIS = {'cantucci': '82867'}

cache = {
    'data': DATA,
    'gerado_em': str(date.today()),
    'semana_inicio': SEMANA_INICIO,
    'lojas': {},
    'vmarket': {},
    'erros': [],
}
for lid, _, __ in LOJAS_OS:
    cache['lojas'][lid] = {
        'faturamento': None, 'meta': None,
        'google': None, 'ifood': None, 'reviews_dia': None,
        'relatorio': None,
        'quadro': None,
        'diarias': None,
        'checklists': None,
        'maturidade': None,
    }

# Checklists esperados por unidade por dia (tipos × 2 turnos)
# Ajustar conforme mudanças nos processos de cada unidade
CHECKLIST_ESPERADO = {
    'cantucci_an':      8,   # 4 tipos × 2 turnos
    'cantucci_as':      12,  # 6 tipos × 2 turnos
    'cantucci_ac':      12,  # 6 tipos × 2 turnos
    'superquadra':      14,  # 7 tipos × 2 turnos
    'mane':             12,  # Superquadra Mané + Véi Chico
    'koji':             4,   # estimativa
}

def log(msg):
    print(f'  {msg}')

# ─── 1. Cantucci OS ───────────────────────────────────────────────────────────
def sync_cantucci_os():
    log('Cantucci OS...')
    try:
        r = requests.post('https://cantuccidados.com.br/api/auth/login',
                          data={'username': CANTUCCI_OS_USER, 'password': CANTUCCI_OS_PASS}, timeout=10)
        tok = r.json().get('access_token')
        if not tok: raise Exception('token vazio')
        h = {'Authorization': f'Bearer {tok}'}

        def fetch(row):
            lid, api_id, _ = row
            d = requests.get('https://cantuccidados.com.br/api/gestao/diario',
                             params={'data': DATA, 'loja': api_id, 'turno': 'todos'}, headers=h, timeout=10)
            m = requests.get('https://cantuccidados.com.br/api/metas/dia',
                             params={'data': DATA, 'lojas': api_id}, headers=h, timeout=10)
            fat  = d.json().get('atual', {}).get('faturamento') if d.ok else None
            meta = m.json().get('meta_sem_servico') if m.ok else None
            return lid, fat, meta

        with ThreadPoolExecutor(max_workers=7) as ex:
            results = list(ex.map(fetch, LOJAS_OS))

        for lid, fat, meta in results:
            if fat is not None:
                prev = cache['lojas'][lid]['faturamento'] or 0
                cache['lojas'][lid]['faturamento'] = round(prev + fat, 2)
            if meta is not None:
                prev = cache['lojas'][lid]['meta'] or 0
                cache['lojas'][lid]['meta'] = round(prev + meta, 2)

        log(f'OS OK — {sum(1 for _,f,_ in results if f)} unidades com faturamento')
    except Exception as e:
        cache['erros'].append(f'cantucci_os: {e}')
        log(f'OS ERRO: {e}')

# ─── 2. Falaê reputação (Google + iFood) ─────────────────────────────────────
def sync_falae():
    log('Falaê...')
    try:
        r = requests.post('https://api-b2s.experienciab2s.com/sessions',
                          json={'email': FALAE_EMAIL, 'password': FALAE_SENHA}, timeout=10)
        tok = r.json()['token']
        user_cid = r.json()['user']['company_id']
        h = {'Authorization': f'Bearer {tok}', 'company_id': user_cid}
        start = str(DATA_DT - timedelta(days=30))

        def fetch_reviews_baixas(cid, plat):
            """Busca textos das avaliações com nota <= 2 do dia."""
            endpoint = {
                'google': 'https://api-b2s.experienciab2s.com/integrations/reviewsGoogle/pagination',
                'ifood':  'https://api-b2s.experienciab2s.com/integrations/ifood/pagination',
            }[plat]
            campo_nota    = 'grade'
            campo_comment = 'comment'
            campo_cliente = {'google': 'client_name', 'ifood': 'customer'}[plat]
            try:
                r = requests.get(endpoint,
                                 params={'companies_id': cid, 'date_start': DATA, 'date_end': DATA,
                                         'offset': 1, 'limit': 50},
                                 headers={**h, 'company_id': cid}, timeout=10)
                if not r.ok: return []
                items = r.json().get('data', r.json()) if isinstance(r.json(), dict) else r.json()
                if not isinstance(items, list): items = []
                baixas = []
                for it in items:
                    nota = it.get(campo_nota) or 0
                    if nota <= 2:
                        cliente = it.get(campo_cliente) or 'Anônimo'
                        texto   = (it.get(campo_comment) or '').strip()
                        baixas.append({'nota': nota, 'cliente': cliente, 'texto': texto})
                return baixas
            except Exception:
                return []

        def fetch_rep(lid):
            cids = FALAE_COMPANIES.get(lid, [])
            if not cids: return lid, [], [], {}
            reps30, repsdia = [], []
            baixas_textos = {'google': [], 'ifood': []}
            for cid in cids:
                rr = requests.get('https://api-b2s.experienciab2s.com/dashboard/reputation',
                                  params={'companies_id': cid, 'date_start': start, 'date_end': DATA},
                                  headers={**h, 'company_id': cid}, timeout=10)
                rd = requests.get('https://api-b2s.experienciab2s.com/dashboard/reputation',
                                  params={'companies_id': cid, 'date_start': DATA, 'date_end': DATA},
                                  headers={**h, 'company_id': cid}, timeout=10)
                if rr.ok: reps30.append(rr.json())
                if rd.ok:
                    rdj = rd.json()
                    repsdia.append(rdj)
                    for plat in ['google', 'ifood']:
                        bxs = ((rdj.get(plat, {}).get('summary', {}).get('oneStar') or 0) +
                               (rdj.get(plat, {}).get('summary', {}).get('twoStars') or 0))
                        if bxs:
                            baixas_textos[plat] += fetch_reviews_baixas(cid, plat)
            return lid, reps30, repsdia, baixas_textos

        def media_grade(reps, plat):
            grades = [r.get(plat, {}).get('summary', {}).get('grade')
                      for r in reps if r.get(plat, {}).get('summary', {}).get('grade')]
            totais = [r.get(plat, {}).get('summary', {}).get('total', 0) or 0
                      for r in reps]
            if not grades: return None, None
            return round(sum(grades) / len(grades), 2), sum(totais)

        with ThreadPoolExecutor(max_workers=4) as ex:
            results = list(ex.map(fetch_rep, list(FALAE_COMPANIES.keys())))

        ok = 0
        for lid, reps30, repsdia, baixas_textos in results:
            g_grade, g_total = media_grade(reps30, 'google')
            i_grade, i_total = media_grade(reps30, 'ifood')
            if g_grade or i_grade:
                cache['lojas'][lid]['google'] = {'grade': g_grade, 'total': g_total} if g_grade else None
                cache['lojas'][lid]['ifood']  = {'grade': i_grade, 'total': i_total} if i_grade else None
                reviews_dia = {}
                for plat in ['google', 'ifood']:
                    tot = sum((r.get(plat, {}).get('summary', {}).get('total') or 0) for r in repsdia)
                    bxs = sum(((r.get(plat, {}).get('summary', {}).get('oneStar') or 0) +
                               (r.get(plat, {}).get('summary', {}).get('twoStars') or 0)) for r in repsdia)
                    if tot:
                        reviews_dia[plat] = {'total': tot, 'baixas': bxs,
                                             'textos': baixas_textos.get(plat, [])}
                cache['lojas'][lid]['reviews_dia'] = reviews_dia or None
                ok += 1
        log(f'Falaê OK — {ok} unidades com reputação')
    except Exception as e:
        cache['erros'].append(f'falae: {e}')
        log(f'Falaê ERRO: {e}')

# ─── 3. Quadro Operacional ────────────────────────────────────────────────────
def sync_quadro():
    log('Quadro Operacional...')
    try:
        result = subprocess.run(
            [sys.executable, 'quadro_mapear_tudo.py'], cwd=DIR,
            capture_output=True, text=True, timeout=60, encoding='utf-8', errors='replace'
        )
        with open(os.path.join(DIR, 'QUADRO_DADOS.json'), encoding='utf-8') as f:
            raw = json.load(f)

        items = raw if isinstance(raw, list) else raw.get('quadros', [])
        for q in items:
            if q.get('data') != DATA: continue
            lid = slug_to_lid(q.get('unidade', ''))
            if not lid: continue
            if cache['lojas'][lid]['quadro'] is None:
                cache['lojas'][lid]['quadro'] = {'freelas': 0, 'alerta_escala': False,
                                                  'alerta_rupturas': False, 'rupturas': [], 'turnos': 0}
            qd = cache['lojas'][lid]['quadro']
            qd['turnos'] += 1
            qd['freelas'] += q.get('freelas', 0)
            if q.get('alerta_escala'):   qd['alerta_escala'] = True
            if q.get('alerta_rupturas'): qd['alerta_rupturas'] = True
            for itens in (q.get('rupturas') or {}).values():
                qd['rupturas'] += itens

        log(f'Quadro OK')
    except Exception as e:
        cache['erros'].append(f'quadro: {e}')
        log(f'Quadro ERRO: {e}')

# ─── 4. Relatório pós-turno ───────────────────────────────────────────────────
def sync_relatorio():
    log('Relatório pós-turno...')
    try:
        subprocess.run(
            [sys.executable, 'relatorio_mapear_tudo.py'], cwd=DIR,
            capture_output=True, text=True, timeout=60, encoding='utf-8', errors='replace'
        )
        with open(os.path.join(DIR, 'RELATORIO_DADOS.json'), encoding='utf-8') as f:
            raw = json.load(f)

        items = raw.get('relatorios_unidades', [])
        mane  = raw.get('relatorios_mane', [])

        # Relatórios submetidos hoje antes das 10h também pertencem ao turno anterior (DATA)
        from datetime import datetime as _dt
        hoje = str(date.today())
        corte_ts = _dt.combine(date.today(), _dt.min.time().replace(hour=10)).timestamp() * 1000

        agg = {}
        for r in items + mane:
            dt = (r.get('date') or r.get('reportDate') or '')[:10]
            ts = r.get('timestamp', 0) or 0
            # aceita: data == DATA, ou data == hoje E enviado antes das 10h
            if dt == DATA:
                pass
            elif dt == hoje and ts and ts < corte_ts:
                pass  # relatório da madrugada — pertence ao turno anterior
            else:
                continue
            unit = r.get('unit', '').lower().replace('_', '-')
            # Mané vem com encoding corrompido do Firestore — normaliza para o slug correto
            if unit.startswith('man'):
                unit = 'mane'
            if unit not in agg:
                agg[unit] = {'notas': [], 'tmas': [], 'ocs': [], 'bos': []}
            if r.get('notaTurno') is not None: agg[unit]['notas'].append(float(r['notaTurno']))
            tma = r.get('tma') or r.get('tmaAverage')
            if tma is not None: agg[unit]['tmas'].append(float(tma))
            for flag, label in [
                ('temAtraso','Atraso cozinha'), ('temErroQualidade','Erro qualidade'),
                ('temReclamacaoAtendimento','Reclamação'), ('temReclamacaoRuptura','Ruptura salão'),
                ('deliveryAtraso','Delivery atraso'), ('equipamentoQuebrado','Equip. quebrado'),
                ('hadFoodErrors','Erro prato'), ('hadCustomerComplaints','Reclamação cliente'),
            ]:
                if r.get(flag): agg[unit]['ocs'].append(label)
            if r.get('principalBO'): agg[unit]['bos'].append(r['principalBO'])

        for lid, slug in LOJA_SLUG.items():
            rel = agg.get(slug)
            if rel:
                notas = rel['notas']
                cache['lojas'][lid]['relatorio'] = {
                    'nota_min': min(notas) if notas else None,
                    'nota_max': max(notas) if notas else None,
                    'nota_med': round(sum(notas)/len(notas), 1) if notas else None,
                    'turnos':   len(notas),
                    'tma':      round(sum(rel['tmas'])/len(rel['tmas'])) if rel['tmas'] else None,
                    'ocs':      list(dict.fromkeys(rel['ocs'])),
                    'bos':      rel['bos'],
                }
        log(f'Relatório OK — {len(agg)} unidades com dados')
    except Exception as e:
        cache['erros'].append(f'relatorio: {e}')
        log(f'Relatório ERRO: {e}')

# ─── 5. Dashboard 3V (diárias) ────────────────────────────────────────────────
def sync_dashboard3v():
    log('Dashboard 3V...')
    try:
        subprocess.run(
            [sys.executable, 'dashboard3v_mapear.py'], cwd=DIR,
            capture_output=True, text=True, timeout=120, encoding='utf-8', errors='replace'
        )
        with open(os.path.join(DIR, 'DASHBOARD3V_DADOS.json'), encoding='utf-8') as f:
            raw = json.load(f)

        dashboard = raw.get('dashboard', {})
        for lid, key_3v in LOJA_3V.items():
            data_un = dashboard.get(key_3v, {})
            txt = data_un.get('_raw_text', '')
            m = re.search(r'Diárias\s+R\$[\xa0\s]*([\d.,]+)\s+R\$[\xa0\s]*([\d.,]+)\s+([\d.,]+%)', txt)
            if m:
                cache['lojas'][lid]['diarias'] = {
                    'acumulado': m.group(1), 'meta': m.group(2), 'pct': m.group(3)
                }
        log(f'3V OK — {sum(1 for l in cache["lojas"].values() if l["diarias"])} unidades com diárias')
    except Exception as e:
        cache['erros'].append(f'dashboard3v: {e}')
        log(f'3V ERRO: {e}')

# ─── 6. VMarket ───────────────────────────────────────────────────────────────
VMARKET_CREDS = [
    ('cantucci',       'admin@cantucci.com.br',       'Mudar102030@@'),
    ('cantuccisul',    'admin@cantuccisul.com.br',    'Mudar102030@@'),
    ('infornoburguer', 'admin@infornoburguer.com.br', 'Mudar102030@@'),
]
BROWSER_HEADERS = {
    'Origin':  'https://vmarketcompras.com.br',
    'Referer': 'https://vmarketcompras.com.br/',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
}

def sync_vmarket():
    log('VMarket...')
    try:
        API = 'https://39lwlzahue.execute-api.us-east-1.amazonaws.com'

        def fetch_empresa(emp, email, senha):
            r_login = requests.post('https://vmarketcompras.com.br/app/vmarket-core/usuario/login',
                json={'email': email, 'senha': senha}, timeout=10)
            dados = r_login.json().get('dados', {})
            filial = dados.get('id_fornecedor')
            if not filial:
                return emp, {}

            sess_path = os.path.join(DIR, 'vmarket_session.json')
            sess = json.load(open(sess_path, encoding='utf-8')) if os.path.exists(sess_path) else {}
            jwt = sess.get(emp, {}).get('auth_headers', {}).get('authorization', '')
            if not jwt:
                return emp, {}
            h = {'Authorization': jwt, **BROWSER_HEADERS}

            # Usa /pedidos com paginação por 'page' para excluir cancelados (status 6)
            # Sem id_filial — o JWT determina a empresa. periodo_ate é exclusivo (+1 dia).
            STATUS_CANCELADO = {6}
            DATA_ATE = str(DATA_DT + timedelta(days=1))
            by_pid = {}
            page = 1
            while True:
                rp = requests.get(f'{API}/pedidos',
                    params={'periodo_de': SEMANA_INICIO, 'periodo_ate': DATA_ATE, 'page': page},
                    headers=h, timeout=15)
                if not rp.ok: break
                d = rp.json().get('dados', {})
                items = d.get('data', [])
                last_page = d.get('last_page', 1)
                for p in items:
                    pid = p.get('id_pedido')
                    if pid and pid not in by_pid:
                        by_pid[pid] = p
                if page >= last_page or not items: break
                page += 1

            ativos = [p for p in by_pid.values() if p.get('id_pedido_status') not in STATUS_CANCELADO]
            total_val = sum(float(p.get('total') or 0) for p in ativos)
            return emp, {
                'total': total_val,
                'pedidos': len(ativos),
                'cotacoes': 0,
            }

        with ThreadPoolExecutor(max_workers=3) as ex:
            results = list(ex.map(lambda x: fetch_empresa(*x), VMARKET_CREDS))

        for emp, d in results:
            if d:
                cache['vmarket'][emp] = d

        log(f'VMarket OK — {len(cache["vmarket"])} empresas')
    except Exception as e:
        cache['erros'].append(f'vmarket: {e}')
        log(f'VMarket ERRO: {e}')

# ─── 7. Checklists (ChecklistFácil) ──────────────────────────────────────────
CHECKLIST_UNIDADE_MAP = {
    'cantucci asa norte':    'cantucci_an',
    'cantucci asa sul':      'cantucci_as',
    'cantucci águas claras': 'cantucci_ac',
    'cantucci aguas claras': 'cantucci_ac',
    'superquadra norte':     'superquadra',
    'superquadra mané':      'mane',
    'superquadra mane':      'mane',
    'véi chico':             'mane',
    'vei chico':             'mane',
    'mané':                  'mane',
    'koji asa sul':          'koji',
    'koji':                  'koji',
}

def sync_checklists():
    log('Checklists...')
    try:
        data_br = DATA_DT.strftime('%d/%m/%Y')
        subprocess.run(
            [sys.executable, 'checklistfacil_consultar.py', data_br], cwd=DIR,
            capture_output=True, text=True, timeout=90, encoding='utf-8', errors='replace'
        )
        res_path = os.path.join(DIR, 'checklistfacil_resultado.json')
        if not os.path.exists(res_path):
            log('Checklists: resultado.json não encontrado (cookies expirados?)')
            return
        with open(res_path, encoding='utf-8') as f:
            raw = json.load(f)
        # Verifica se os dados são do dia correto
        if raw.get('data') != data_br:
            log(f'Checklists: cache é de {raw.get("data")} — cookies expirados?')
            return
        # Conta execuções concluídas por unidade
        counts = {}
        for ex in raw.get('execucoes', []):
            if ex.get('status') != 'Concluído':
                continue
            u = ex.get('unidade', '').lower().strip()
            lid = None
            for k, v in CHECKLIST_UNIDADE_MAP.items():
                if k in u:
                    lid = v
                    break
            if lid:
                counts[lid] = counts.get(lid, 0) + 1
        for lid, n in counts.items():
            if lid in cache['lojas']:
                cache['lojas'][lid]['checklists'] = n
        total = sum(counts.values())
        log(f'Checklists OK — {total} execuções em {len(counts)} unidades')
    except Exception as e:
        cache['erros'].append(f'checklists: {e}')
        log(f'Checklists ERRO: {e}')

# ─── 8. Maturidade Operacional ────────────────────────────────────────────────
def calcular_maturidade():
    """
    Score 0-10, meta >= 7.
    3 componentes de peso igual (33% cada):
      - Quadro operacional: meta 2 turnos/dia
      - Relatório pós-turno: meta 2 turnos/dia
      - Checklists: meta = CHECKLIST_ESPERADO[unidade]
    Se checklists não disponíveis, pondera apenas quadro + relatório (50% max).
    """
    for lid in cache['lojas']:
        loja = cache['lojas'][lid]

        q_turnos = (loja.get('quadro') or {}).get('turnos', 0)
        r_turnos = (loja.get('relatorio') or {}).get('turnos', 0)
        ck_exec  = loja.get('checklists') or 0
        ck_esp   = CHECKLIST_ESPERADO.get(lid, 4)

        q_score  = min(q_turnos, 2) / 2 * 10
        r_score  = min(r_turnos, 2) / 2 * 10
        ck_score = min(ck_exec / ck_esp, 1.0) * 10 if ck_esp > 0 else 0

        if ck_exec > 0:
            score = round((q_score + r_score + ck_score) / 3, 1)
            tem_ck = True
        else:
            # Sem dados de checklist — pontua apenas o que temos (máx 6.7)
            score = round((q_score + r_score) / 3, 1)  # /3 para manter escala honesta
            tem_ck = False

        loja['maturidade'] = {
            'score':               score,
            'quadro_turnos':       q_turnos,
            'relatorio_turnos':    r_turnos,
            'checklist_executado': ck_exec,
            'checklist_esperado':  ck_esp,
            'tem_checklist':       tem_ck,
        }

# ─── Helpers ──────────────────────────────────────────────────────────────────
SLUG_MAP = {
    'asa norte': 'cantucci_an', 'asa sul': 'cantucci_as',
    'aguas claras': 'cantucci_ac', 'águas claras': 'cantucci_ac',
    'superquadra norte': 'superquadra', 'superquadra man': 'mane',
    'mané': 'mane', 'mane': 'mane',
    'véi chico': 'mane', 'vei chico': 'mane',
    'koji': 'koji',
}
def slug_to_lid(name):
    n = name.lower().strip()
    for k, v in SLUG_MAP.items():
        if k in n: return v
    return None

# ─── Main ─────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    print(f'\n🔄 SYNC DIÁRIO — {DATA}')
    print('─' * 40)

    # Paralelo: OS + Falaê + Quadro + Relatório
    # 3V e VMarket têm Playwright, rodam em série pra não travar
    with ThreadPoolExecutor(max_workers=4) as ex:
        futs = [
            ex.submit(sync_cantucci_os),
            ex.submit(sync_falae),
            ex.submit(sync_quadro),
            ex.submit(sync_relatorio),
        ]
        for f in futs: f.result()

    sync_dashboard3v()
    sync_vmarket()
    sync_checklists()
    calcular_maturidade()

    # Checklist indisponivel no plano atual — nao e erro, apenas sem dados
    sem_checklist = all(cache['lojas'][lid].get('checklists') is None for lid in cache['lojas'])
    if sem_checklist:
        msg = 'Checklist Facil: sem dados (API nao disponivel no plano atual)'
        print(f'\n⚠️  {msg}')
        try:
            if sys.platform == 'win32':
                subprocess.run(
                    ['powershell', '-Command',
                     f'Add-Type -AssemblyName System.Windows.Forms; '
                     f'[System.Windows.Forms.MessageBox]::Show("{msg}", "Alerta Cantucci Daily")'],
                    timeout=5, capture_output=True
                )
        except Exception:
            pass

    # Salva cache
    cache_path = os.path.join(DIR, 'DAILY_CACHE.json')
    with open(cache_path, 'w', encoding='utf-8') as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)

    # Acumula histórico diário (faturamento + maturidade)
    LOJAS_LABEL = {
        'cantucci_an': 'Cantucci Asa Norte', 'cantucci_as': 'Cantucci Asa Sul',
        'cantucci_ac': 'Cantucci Águas Claras', 'superquadra': 'Superquadra Norte',
        'mane': 'Mané', 'koji': 'Koji',
    }
    hist_path = os.path.join(DIR, 'HISTORICO_DIARIO.json')
    historico = []
    if os.path.exists(hist_path):
        with open(hist_path, encoding='utf-8') as f:
            historico = json.load(f)
    historico = [h for h in historico if h.get('data') != DATA]
    for lid, loja in cache['lojas'].items():
        mat = loja.get('maturidade') or {}
        historico.append({
            'data':                 DATA,
            'unidade_id':           lid,
            'unidade':              LOJAS_LABEL.get(lid, lid),
            'faturamento':          loja.get('faturamento'),
            'meta':                 loja.get('meta'),
            'maturidade_score':     mat.get('score'),
            'quadro_turnos':        mat.get('quadro_turnos', 0),
            'relatorio_turnos':     mat.get('relatorio_turnos', 0),
            'checklist_executado':  mat.get('checklist_executado', 0),
            'checklist_esperado':   mat.get('checklist_esperado', 0),
            'tem_checklist':        mat.get('tem_checklist', False),
        })
    historico.sort(key=lambda x: (x['data'], x['unidade_id']))
    with open(hist_path, 'w', encoding='utf-8') as f:
        json.dump(historico, f, ensure_ascii=False, indent=2)

    # Mantém HISTORICO_MATURIDADE.json para compatibilidade
    hist_mat_path = os.path.join(DIR, 'HISTORICO_MATURIDADE.json')
    hist_mat = [h for h in historico if h.get('maturidade_score') is not None]
    with open(hist_mat_path, 'w', encoding='utf-8') as f:
        json.dump(hist_mat, f, ensure_ascii=False, indent=2)

    log(f'Histórico diário: {len(historico)} registros')

    # Gera relatório HTML (o workflow do GitHub Actions faz o commit/push)
    subprocess.run(
        [sys.executable, 'daily_html.py', DATA], cwd=DIR,
        capture_output=True, text=True, encoding='utf-8', errors='replace'
    )
    log('DAILY_REPORT.html gerado')
    # No CI, o commit/push é feito pelo workflow — só roda localmente
    if not os.environ.get('GITHUB_ACTIONS'):
        try:
            import shutil
            shutil.copy(os.path.join(DIR, 'DAILY_REPORT.html'), os.path.join(DIR, 'index.html'))
            subprocess.run(['git', 'add', 'index.html'], cwd=DIR, capture_output=True)
            subprocess.run(['git', 'commit', '-m', f'Report {DATA}'], cwd=DIR, capture_output=True)
            subprocess.run(['git', 'push'], cwd=DIR, capture_output=True)
            log('GitHub Pages atualizado')
        except Exception as e:
            log(f'GitHub Pages ERRO: {e}')

    ok = sum(1 for l in cache['lojas'].values()
             if any(v is not None for v in l.values()))
    print(f'\n✅ Cache salvo — {ok}/7 unidades com dados')
    if cache['erros']:
        print(f'⚠️  Erros: {", ".join(cache["erros"])}')
