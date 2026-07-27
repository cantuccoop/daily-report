"""
weekly_report.py — Lê WEEKLY_CACHE.json e imprime o report semanal
Instantâneo — zero requisições de rede.

Uso: py -3 weekly_report.py [YYYY-MM-DD]   (data dentro da semana; sem argumento = semana passada)
"""
import sys, json, os
from datetime import date, timedelta

sys.stdout.reconfigure(encoding='utf-8')

DIR = os.path.dirname(os.path.abspath(__file__))

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


def semaforo_pct(pct):
    if pct is None: return ''
    if pct >= 100: return '✅'
    if pct >= 80: return '⚠️'
    return '🔴'


def semaforo_mat(score):
    if score is None: return ''
    if score >= 7: return '✅'
    if score >= 5: return '⚠️'
    return '🔴'


def load_cache():
    path = os.path.join(DIR, 'WEEKLY_CACHE.json')
    if not os.path.exists(path):
        return None, 'WEEKLY_CACHE.json não encontrado — rode: py -3 weekly_sync.py'
    with open(path, encoding='utf-8') as f:
        c = json.load(f)
    if c.get('semana_inicio') != SEGUNDA.isoformat():
        return c, f'⚠️  Cache é da semana de {c.get("semana_inicio")} — dados podem estar desatualizados'
    return c, None


cache, warn = load_cache()
if not cache:
    print(warn)
    sys.exit(1)

SEP = '═' * 54
print(f'\n📅 REPORT SEMANAL — {SEGUNDA.strftime("%d/%m")} a {DOMINGO.strftime("%d/%m/%Y")}')
if warn: print(warn)
print(SEP)

for lid, label in LOJAS:
    loja = cache['lojas'].get(lid, {})
    print(f'\n🏠 {label.upper()}')

    fat = loja.get('faturamento')
    meta = loja.get('meta')
    if fat and meta and meta > 0:
        pct = round(fat / meta * 100)
        print(f'💰 Faturamento   → R$ {fat:>10,.0f}  /  meta R$ {meta:,.0f}  ({pct}%) {semaforo_pct(pct)}')
    elif fat:
        print(f'💰 Faturamento   → R$ {fat:>10,.0f}  (sem meta cadastrada)')
    else:
        print(f'💰 Faturamento   → —')

    g = loja.get('google')
    i = loja.get('ifood')
    rs = loja.get('reviews_semana') or {}
    det_g = loja.get('detratores_google')
    det_i = loja.get('detratores_ifood')
    if g or i:
        g_str = f'⭐{g["grade"]:.1f} ({g["total"]})' if g and g.get('grade') else '—'
        i_str = f'⭐{i["grade"]:.1f} ({i["total"]})' if i and i.get('grade') else '—'
        det_total = (det_g or 0) + (det_i or 0)
        det_str = f'  |  {det_total} detrator(es) (≤2★)' if det_total else '  |  0 detratores'
        print(f'⭐ Reputação     → Google {g_str} | iFood {i_str}{det_str}')
        for plat, plabel in [('google', 'Google'), ('ifood', 'iFood')]:
            s = rs.get(plat)
            if s and s.get('baixas'):
                print(f'   ↳ ⚠️ {s["baixas"]} avaliação(ões) {plabel} abaixo de 3★ na semana')
                for t in s.get('textos', [])[:5]:
                    estrelas = '⭐' * int(t.get('nota', 1))
                    texto = t.get('texto', '').strip()
                    linha = f'      • {estrelas} {t.get("cliente", "Anônimo")}'
                    if texto:
                        linha += f': "{texto[:120]}"'
                    print(linha)
    else:
        print(f'⭐ Reputação     → —')

    dias = loja.get('dias', 0) or 0
    q_t = loja.get('quadro_turnos', 0)
    r_t = loja.get('relatorio_turnos', 0)
    ck_e = loja.get('checklist_executado', 0)
    ck_esp = loja.get('checklist_esperado', 0)
    mat = loja.get('maturidade_media')
    ops_str = f'quadro {q_t}/{dias * 2} | turno {r_t}/{dias * 2} | ck {ck_e}/{ck_esp}'
    if mat is not None:
        print(f'🎯 Maturidade Op.→ média {mat}/10 {semaforo_mat(mat)}  {ops_str}')
    else:
        print(f'🎯 Maturidade Op.→ —  {ops_str}')

    cmc = loja.get('cmc_semana_pct')
    cmv = loja.get('cmv_mes_pct')
    cmv_meta = loja.get('cmv_mes_meta_pct')
    mes_ref = cache.get('mes_referencia_cmv') or '—'
    if cmc is not None:
        print(f'🧾 CMC semana    → {cmc}%')
    else:
        print(f'🧾 CMC semana    → —')
    if cmv is not None:
        meta_str = f' (meta {cmv_meta}%)' if cmv_meta is not None else ''
        print(f'📦 CMV mês ({mes_ref}) → {cmv}%{meta_str}')
    else:
        print(f'📦 CMV mês       → —')

    pct_deliv = loja.get('pct_delivery')
    if pct_deliv is not None:
        print(f'🛵 Delivery      → {pct_deliv}%')
    else:
        print(f'🛵 Delivery      → —')

    desc_qtd = loja.get('descontos_qtd')
    desc_val = loja.get('descontos_valor')
    if desc_qtd is not None:
        print(f'🏷️ Descontos     → {desc_qtd} descontos  |  R$ {desc_val:,.2f}')
    else:
        print(f'🏷️ Descontos     → —')

    pct_up = loja.get('pct_upsell')
    pct_alc = loja.get('pct_alcoolica')
    if pct_up is not None or pct_alc is not None:
        up_str = f'{pct_up}% upsell' if pct_up is not None else 'upsell —'
        alc_str = f'{pct_alc}% alcoólica' if pct_alc is not None else 'alcoólica —'
        print(f'🍷 Up/Alcoólica  → {up_str}  |  {alc_str}')
    else:
        print(f'🍷 Up/Alcoólica  → —')

    tma_coz = loja.get('tma_cozinha_min')
    pct_20 = loja.get('pct_tma_acima_20')
    if tma_coz is not None or pct_20 is not None:
        coz_str = f'{tma_coz}min cozinha' if tma_coz is not None else 'cozinha —'
        p20_str = f'{pct_20}% acima de 20min' if pct_20 is not None else '% acima de 20min —'
        print(f'⏱️ TMA           → {coz_str}  |  {p20_str}')
    else:
        print(f'⏱️ TMA           → —')

    proj = loja.get('projecao_mes')
    proj_meta = loja.get('meta_mes')
    proj_pct = loja.get('projecao_pct_meta')
    mes_ref_proj = cache.get('mes_referencia_projecao') or '—'
    if proj is not None:
        meta_str = f' / meta R$ {proj_meta:,.0f} ({proj_pct}%) {semaforo_pct(proj_pct)}' if proj_meta else ''
        print(f'📈 Projeção ({mes_ref_proj}) → R$ {proj:,.0f}{meta_str}')
    else:
        print(f'📈 Projeção      → —')

print(f'\n{SEP}')
if cache.get('erros'):
    print(f'\n⚠️  Fontes com erro na última sync: {", ".join(cache["erros"])}')
print(f'\n{SEP}')
print(f'Cache gerado em: {cache.get("gerado_em", "—")}')
