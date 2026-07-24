"""
daily_report.py — Lê DAILY_CACHE.json e imprime o report matinal
Instantâneo — zero requisições de rede.

Uso: py -3 daily_report.py [YYYY-MM-DD]   (sem argumento = ontem)
"""
import sys, json, os
from datetime import date, timedelta

sys.stdout.reconfigure(encoding='utf-8')

DATA = sys.argv[1] if len(sys.argv) > 1 else str(date.today() - timedelta(days=1))
DIR  = os.path.dirname(os.path.abspath(__file__))

LOJAS = [
    ('cantucci_an',     'Cantucci Asa Norte'),
    ('cantucci_as',     'Cantucci Asa Sul'),
    ('cantucci_ac',     'Cantucci Águas Claras'),
    ('superquadra',     'Superquadra Norte'),
    ('mane',            'Mané'),
    ('koji',            'Koji'),
]

def semaforo_pct(pct):
    if pct is None: return ''
    if pct >= 100:  return '✅'
    if pct >= 80:   return '⚠️'
    return '🔴'

def semaforo_nota(nota):
    if nota is None: return ''
    if nota >= 8:   return '✅'
    if nota >= 6:   return '⚠️'
    return '🔴'

def fmt_brl(txt):
    """R$ 3.564,42 → já formatado, apenas garante o prefixo."""
    return f'R$ {txt}' if txt and not txt.startswith('R$') else (txt or '—')

def load_cache(target_date):
    path = os.path.join(DIR, 'DAILY_CACHE.json')
    if not os.path.exists(path):
        return None, 'DAILY_CACHE.json não encontrado — rode: py -3 daily_sync.py'
    with open(path, encoding='utf-8') as f:
        c = json.load(f)
    if c.get('data') != target_date:
        return c, f'⚠️  Cache é de {c.get("data")} — dados podem estar desatualizados'
    return c, None

# ─── Main ─────────────────────────────────────────────────────────────────────
cache, warn = load_cache(DATA)
if not cache:
    print(warn)
    sys.exit(1)

DATA_DT = date.fromisoformat(DATA)
SEP = '═' * 54

print(f'\n☀️  REPORT MATINAL — {DATA_DT.strftime("%d/%m/%Y")}')
if warn: print(warn)
print(SEP)

for lid, label in LOJAS:
    loja = cache['lojas'].get(lid, {})
    print(f'\n🏠 {label.upper()}')

    # Faturamento
    fat  = loja.get('faturamento')
    meta = loja.get('meta')
    if fat and meta and meta > 0:
        pct = round(fat / meta * 100)
        print(f'💰 Faturamento   → R$ {fat:>9,.0f}  /  meta R$ {meta:,.0f}  ({pct}%) {semaforo_pct(pct)}')
    elif fat:
        print(f'💰 Faturamento   → R$ {fat:>9,.0f}  (sem meta cadastrada)')
    else:
        print(f'💰 Faturamento   → —')

    # Relatório pós-turno
    rel = loja.get('relatorio')
    if rel:
        nmin = rel.get('nota_min')
        nmax = rel.get('nota_max')
        nmed = rel.get('nota_med')
        tma  = rel.get('tma')
        ocs  = rel.get('ocs', [])
        if nmin is not None and nmax is not None:
            if nmin == nmax:
                nota_str = f'{nmed}/10 {semaforo_nota(nmed)}'
            else:
                nota_str = f'{nmin}-{nmax}/10 (média {nmed}) {semaforo_nota(nmin)}'
        else:
            nota_str = '—'
        tma_str  = f'{tma}min' if tma else '—'
        ocs_str  = ', '.join(ocs) if ocs else 'sem ocorrências ✅'
        print(f'📋 Rel. turno    → nota {nota_str} | TMA: {tma_str} | {ocs_str}')
        bos = rel.get('bos', [])
        for bo in bos[:3]:
            print(f'   ↳ {bo[:90]}')
    else:
        print(f'📋 Rel. turno    → —')

    # Quadro operacional
    quad = loja.get('quadro')
    if quad:
        esc = '⚠️ alerta' if quad.get('alerta_escala') else '✅'
        if quad.get('alerta_rupturas'):
            itens = ', '.join(quad.get('rupturas', [])[:3])
            rup = f'🔴 {itens}'
        else:
            rup = '✅ sem rupturas'
        print(f'👥 Quadro Op.    → {quad.get("freelas",0)} freelas | escala {esc} | {rup}')
    else:
        print(f'👥 Quadro Op.    → —')

    # Falaê
    g = loja.get('google')
    i = loja.get('ifood')
    rd = loja.get('reviews_dia') or {}
    if g or i:
        g_str = f'⭐{g["grade"]:.1f} ({g["total"]})'  if g and g.get('grade') else '—'
        i_str = f'⭐{i["grade"]:.1f} ({i["total"]})'  if i and i.get('grade') else '—'
        # Avaliações do dia
        dia_parts = []
        for plat, label in [('google', 'Google'), ('ifood', 'iFood')]:
            s = rd.get(plat)
            if s and s.get('total'):
                baixas = s['baixas']
                txt = f'{label} +{s["total"]} hoje'
                if baixas:
                    txt += f' ⚠️ {baixas} abaixo de 3★'
                dia_parts.append(txt)
        dia_str = ' | '.join(dia_parts) if dia_parts else None
        print(f'⭐ Falaê         → Google {g_str} | iFood {i_str}')
        if dia_str:
            print(f'   ↳ {dia_str}')
    else:
        print(f'⭐ Falaê         → —')

    # Diárias
    d = loja.get('diarias')
    if d:
        pct_num = float(d['pct'].replace('%','').replace(',','.')) if d.get('pct') else None
        meta_str = f'/ meta {fmt_brl(d["meta"])}' if d.get('meta') else ''
        pct_str  = f'({d["pct"]}) {semaforo_pct(pct_num)}' if d.get('pct') else ''
        print(f'📊 Diárias       → {fmt_brl(d["acumulado"])} {meta_str} {pct_str}')
    else:
        print(f'📊 Diárias       → —')

    # Maturidade Operacional
    mat = loja.get('maturidade')
    if mat:
        score   = mat['score']
        q_t     = mat['quadro_turnos']
        r_t     = mat['relatorio_turnos']
        ck_exec = mat['checklist_executado']
        ck_esp  = mat['checklist_esperado']
        tem_ck  = mat['tem_checklist']
        sem_mat = '✅' if score >= 7 else ('⚠️' if score >= 5 else '🔴')
        ck_str  = f'ck {ck_exec}/{ck_esp}' if tem_ck else 'ck — (cookies expirados)'
        parcial = ' ⚠️parcial' if not tem_ck else ''
        print(f'🎯 Maturidade Op.→ {score}/10 {sem_mat}{parcial}  quadro {q_t}/2 | turno {r_t}/2 | {ck_str}')
    else:
        print(f'🎯 Maturidade Op.→ — (rode sync para calcular)')

# VMarket
print(f'\n{SEP}')
semana = cache.get('semana_inicio', '')
sem_fmt = f'{semana[8:10]}/{semana[5:7]}' if semana else '—'
print(f'🛒 VMARKET — semana {sem_fmt} a {DATA_DT.strftime("%d/%m")}')
vm = cache.get('vmarket', {})
if vm:
    total_g = 0
    for emp, d in vm.items():
        tot = d.get('total', 0) or 0
        ped = d.get('pedidos', 0) or 0
        total_g += tot
        print(f'   {emp.capitalize():<18} R$ {tot:>10,.2f}  ({ped} pedidos)')
    print(f'   {"TOTAL GRUPO":<18} R$ {total_g:>10,.2f}')
else:
    print('   — (sem dados)')

if cache.get('erros'):
    print(f'\n⚠️  Fontes com erro na última sync: {", ".join(cache["erros"])}')
print(f'\n{SEP}')
print(f'Cache gerado em: {cache.get("gerado_em", "—")}')
