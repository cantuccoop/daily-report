"""
cantucci_os_semanal.py — Coleta indicadores semanais direto da API do Cantucci OS
(cantuccidados.com.br) e salva em CANTUCCI_OS_SEMANAL.json.

Indicadores coletados, por unidade, para a semana (segunda a domingo):
  - Delivery: % delivery, ticket médio salão/delivery, ticket médio geral
  - Descontos: quantidade e valor total
  - Upsell: % e valor
  - Bebida alcoólica: % e valor
  - TMA (tempo médio de atendimento): cozinha e bar, via KDS
  - Projeção: projeção de faturamento do mês corrente vs meta (só é mensal — a
    API não calcula projeção por semana)

Uso: py -3 cantucci_os_semanal.py [YYYY-MM-DD]   (data dentro da semana alvo; sem argumento = semana passada)
"""
import sys, os, json, re
from datetime import date, timedelta
import requests

sys.stdout.reconfigure(encoding='utf-8')

_E = os.environ.get
CANTUCCI_OS_USER = _E('CANTUCCI_OS_USER', 'julhyana')
CANTUCCI_OS_PASS = _E('CANTUCCI_OS_PASS', 'julhyana90!')
BASE = 'https://cantuccidados.com.br'
DIR = os.path.dirname(os.path.abspath(__file__))

# Código de loja aceito pela API (endpoints .../resumo e /gestao/kds).
# 'mane' usa o "nome bonito" — a API já retorna o dado combinado das duas
# unidades (Superquadra Mané + Véi Chico Mané) para qualquer um dos dois nomes.
LOJA_CODES = {
    'cantucci_an': 'cantucci_an',
    'cantucci_as': 'cantucci_as',
    'cantucci_ac': 'cantucci_ac',
    'superquadra': 'superquadra',
    'mane': 'Superquadra Mané',
    'koji': 'koji',
}

LOJAS = [
    ('cantucci_an', 'Cantucci Asa Norte'),
    ('cantucci_as', 'Cantucci Asa Sul'),
    ('cantucci_ac', 'Cantucci Águas Claras'),
    ('superquadra', 'Superquadra Norte'),
    ('mane', 'Mané'),
    ('koji', 'Koji'),
]


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
SEGUNDA_ISO, DOMINGO_ISO = SEGUNDA.isoformat(), DOMINGO.isoformat()


def log(msg):
    print(f'  {msg}')


def fix_enc(txt):
    try:
        return txt.encode('latin1').decode('utf-8')
    except Exception:
        return txt


def restaurante_to_lid(nome):
    n = fix_enc(nome)
    if 'Koji' in n:
        return 'koji'
    if 'Mané' in n or 'Chico' in n:
        return 'mane'
    if 'Superquadra' in n:
        return 'superquadra'
    if 'Asa Norte' in n:
        return 'cantucci_an'
    if 'Asa Sul' in n:
        return 'cantucci_as'
    if 'Claras' in n:
        return 'cantucci_ac'
    return None


resultado = {
    'semana_inicio': SEGUNDA_ISO,
    'semana_fim': DOMINGO_ISO,
    'mes_referencia_projecao': None,
    'gerado_em': str(date.today()),
    'lojas': {},
    'erros': [],
}
for lid, _ in LOJAS:
    resultado['lojas'][lid] = {
        'pct_delivery': None, 'ticket_medio_geral': None, 'ticket_salao': None, 'ticket_delivery': None,
        'descontos_qtd': None, 'descontos_valor': None,
        'cancelamentos_qtd': None, 'cancelamentos_valor': None,
        'pct_upsell': None, 'fat_upsell': None,
        'pct_alcoolica': None, 'fat_alcoolica': None,
        'tma_cozinha_min': None, 'pct_tma_acima_20': None,
        'projecao_mes': None, 'meta_mes': None, 'projecao_pct_meta': None,
    }


def get(endpoint, params, headers):
    try:
        r = requests.get(f'{BASE}{endpoint}', params=params, headers=headers, timeout=15)
        return r.json() if r.ok else None
    except Exception:
        return None


log('Login Cantucci OS...')
r = requests.post(f'{BASE}/api/auth/login',
                   data={'username': CANTUCCI_OS_USER, 'password': CANTUCCI_OS_PASS}, timeout=10)
tok = r.json().get('access_token')
if not tok:
    resultado['erros'].append('login: token vazio')
    with open(os.path.join(DIR, 'CANTUCCI_OS_SEMANAL.json'), 'w', encoding='utf-8') as f:
        json.dump(resultado, f, ensure_ascii=False, indent=2)
    print('❌ Login falhou — CANTUCCI_OS_SEMANAL.json salvo vazio')
    sys.exit(1)

H = {'Authorization': f'Bearer {tok}'}

# ─── Projeção do mês (chamada única, não é por loja) ─────────────────────────
log('Projeção do mês...')
try:
    proj = get('/api/tendencia/projecao',
               {'ano': DOMINGO.year, 'mes': DOMINGO.month, 'com_servico': 'true'}, H)
    if proj:
        resultado['mes_referencia_projecao'] = f'{DOMINGO.month:02d}/{DOMINGO.year}'
        acc = {}
        for item in proj.get('restaurantes', []):
            lid = restaurante_to_lid(item.get('restaurante', ''))
            if not lid:
                continue
            acc.setdefault(lid, {'projecao': 0.0, 'meta': 0.0})
            acc[lid]['projecao'] += item.get('projecao') or 0
            acc[lid]['meta'] += item.get('meta') or 0
        for lid, v in acc.items():
            resultado['lojas'][lid]['projecao_mes'] = round(v['projecao'], 2)
            resultado['lojas'][lid]['meta_mes'] = round(v['meta'], 2)
            if v['meta'] > 0:
                resultado['lojas'][lid]['projecao_pct_meta'] = round(v['projecao'] / v['meta'] * 100, 1)
    else:
        resultado['erros'].append('projecao: sem resposta')
except Exception as e:
    resultado['erros'].append(f'projecao: {e}')

# ─── Por unidade ───────────────────────────────────────────────────────────
for lid, label in LOJAS:
    log(f'{label}...')
    code = LOJA_CODES[lid]
    params_range = {'data_inicio': SEGUNDA_ISO, 'data_fim': DOMINGO_ISO, 'loja': code, 'turno': 'todos'}

    delivery = get('/api/delivery/resumo', params_range, H)
    if delivery:
        loja = resultado['lojas'][lid]
        loja['pct_delivery'] = delivery.get('pct_delivery')
        loja['ticket_salao'] = delivery.get('ticket_salao')
        loja['ticket_delivery'] = delivery.get('ticket_delivery') or None
        clientes = (delivery.get('clientes_salao') or 0) + (delivery.get('clientes_delivery') or 0)
        fat = (delivery.get('fat_salao') or 0) + (delivery.get('fat_delivery') or 0)
        loja['ticket_medio_geral'] = round(fat / clientes, 2) if clientes else None
    else:
        resultado['erros'].append(f'delivery {lid}: sem resposta')

    descontos = get('/api/descontos/resumo', params_range, H)
    if descontos:
        total = descontos.get('total', {})
        resultado['lojas'][lid]['descontos_qtd'] = total.get('qtd')
        resultado['lojas'][lid]['descontos_valor'] = total.get('valor')
    else:
        resultado['erros'].append(f'descontos {lid}: sem resposta')

    cancelamentos = get('/api/cancelamentos/resumo',
                         {**params_range, 'incluir_estornos': 'true'}, H)
    if cancelamentos:
        total = cancelamentos.get('total', {})
        resultado['lojas'][lid]['cancelamentos_qtd'] = total.get('qtd')
        resultado['lojas'][lid]['cancelamentos_valor'] = total.get('valor')
    else:
        resultado['erros'].append(f'cancelamentos {lid}: sem resposta')

    upsell = get('/api/upsell/resumo', params_range, H)
    if upsell:
        resultado['lojas'][lid]['pct_upsell'] = upsell.get('pct_upsell')
        resultado['lojas'][lid]['fat_upsell'] = upsell.get('fat_upsell')
    else:
        resultado['erros'].append(f'upsell {lid}: sem resposta')

    alcoolica = get('/api/bebida-alcoolica/resumo', params_range, H)
    if alcoolica:
        resultado['lojas'][lid]['pct_alcoolica'] = alcoolica.get('pct')
        resultado['lojas'][lid]['fat_alcoolica'] = alcoolica.get('fat_alcoolica')
    else:
        resultado['erros'].append(f'alcoolica {lid}: sem resposta')

    kds = get('/api/gestao/kds', {'data_inicio': SEGUNDA_ISO, 'data_fim': DOMINGO_ISO, 'loja': code}, H)
    if kds:
        comida_media = (kds.get('comida') or {}).get('media')
        resultado['lojas'][lid]['tma_cozinha_min'] = comida_media or None
        items = kds.get('comida_items') or []
        if items:
            acima_20 = sum(1 for it in items if (it.get('minutos') or 0) > 20)
            resultado['lojas'][lid]['pct_tma_acima_20'] = round(acima_20 / len(items) * 100, 1)
    else:
        resultado['erros'].append(f'kds {lid}: sem resposta')

out_path = os.path.join(DIR, 'CANTUCCI_OS_SEMANAL.json')
with open(out_path, 'w', encoding='utf-8') as f:
    json.dump(resultado, f, ensure_ascii=False, indent=2)

ok = sum(1 for l in resultado['lojas'].values() if l.get('pct_delivery') is not None)
print(f'\n✅ CANTUCCI_OS_SEMANAL.json salvo — {ok}/{len(LOJAS)} unidades com dados de delivery')
if resultado['erros']:
    print(f'⚠️  Erros: {", ".join(resultado["erros"])}')
