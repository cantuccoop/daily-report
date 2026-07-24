"""
daily_html.py — Gera DAILY_REPORT.html a partir do DAILY_CACHE.json
Uso: py -3 daily_html.py [YYYY-MM-DD]
"""
import sys, json, os
from datetime import date, timedelta, datetime

sys.stdout.reconfigure(encoding='utf-8')

DATA = sys.argv[1] if len(sys.argv) > 1 else str(date.today() - timedelta(days=1))
DIR  = os.path.dirname(os.path.abspath(__file__))

LOJAS = [
    ('cantucci_an',      'Cantucci Asa Norte'),
    ('cantucci_as',      'Cantucci Asa Sul'),
    ('cantucci_ac',      'Cantucci Águas Claras'),
    ('superquadra',      'Superquadra Norte'),
    ('mane',             'Mané'),
    ('koji',             'Koji'),
]

def load_cache():
    path = os.path.join(DIR, 'DAILY_CACHE.json')
    if not os.path.exists(path):
        return None
    with open(path, encoding='utf-8') as f:
        return json.load(f)

def cor_pct(pct):
    if pct is None: return 'gray'
    if pct >= 100:  return 'green'
    if pct >= 80:   return 'yellow'
    return 'red'

def cor_nota(nota):
    if nota is None: return 'gray'
    if nota >= 8:   return 'green'
    if nota >= 6:   return 'yellow'
    return 'red'

def cor_mat(score):
    if score is None: return 'gray'
    if score >= 7:   return 'green'
    if score >= 5:   return 'yellow'
    return 'red'

def badge(cor, texto):
    cores = {
        'green':  ('#e6f4ea', '#2d6a4f', '#52b788'),
        'yellow': ('#fff8e1', '#7d5a00', '#ffc107'),
        'red':    ('#fdecea', '#c0392b', '#e74c3c'),
        'gray':   ('#f5f5f5', '#666',    '#999'),
    }
    bg, txt, border = cores.get(cor, cores['gray'])
    return f'<span style="background:{bg};color:{txt};border:1px solid {border};padding:2px 8px;border-radius:12px;font-size:0.8em;font-weight:600;">{texto}</span>'

def icone_cor(cor):
    return {'green': '✅', 'yellow': '⚠️', 'red': '🔴', 'gray': '—'}.get(cor, '—')

def card_loja(lid, label, loja):
    fat   = loja.get('faturamento')
    meta  = loja.get('meta')
    rel   = loja.get('relatorio') or {}
    quadro= loja.get('quadro') or {}
    google= loja.get('google') or {}
    ifood = loja.get('ifood') or {}
    rd    = loja.get('reviews_dia') or {}
    diarias = loja.get('diarias') or {}
    mat   = loja.get('maturidade') or {}

    # Faturamento
    if fat and meta and meta > 0:
        pct = round(fat / meta * 100)
        c = cor_pct(pct)
        fat_html = f'<b>R$ {fat:,.0f}</b> / meta R$ {meta:,.0f} &nbsp;{badge(c, f"{pct}%")}'
    elif fat:
        fat_html = f'<b>R$ {fat:,.0f}</b> <span style="color:#999">(sem meta)</span>'
    else:
        fat_html = '<span style="color:#999">—</span>'

    # Relatório
    notas = rel.get('nota_min')
    if notas is not None:
        nmin = rel.get('nota_min')
        nmax = rel.get('nota_max')
        nmed = rel.get('nota_med')
        tma  = rel.get('tma')
        ocs  = rel.get('ocs', [])
        bos  = rel.get('bos', [])
        nota_str = f'{nmed}/10' if nmin == nmax else f'{nmin}–{nmax}/10 (média {nmed})'
        cn = cor_nota(nmed)
        ocs_str = ', '.join(ocs) if ocs else 'Sem ocorrências'
        tma_str = f'{tma}min' if tma else '—'
        bos_html = ''.join(f'<div style="color:#555;font-size:0.85em;margin-top:4px">↳ {b[:100]}</div>' for b in bos[:3])
        rel_html = f'''
            {badge(cn, nota_str)} &nbsp; TMA: {tma_str} &nbsp;
            <span style="color:#666;font-size:0.9em">{ocs_str}</span>
            {bos_html}'''
    else:
        rel_html = '<span style="color:#999">—</span>'

    # Quadro
    if quadro:
        esc = '⚠️ alerta' if quadro.get('alerta_escala') else '✅'
        rupt = quadro.get('rupturas', [])
        if quadro.get('alerta_rupturas') and rupt:
            rupt_str = f'🔴 {", ".join(rupt[:3])}'
        else:
            rupt_str = '✅ sem rupturas'
        quadro_html = f'{quadro.get("freelas",0)} freelas &nbsp;|&nbsp; escala {esc} &nbsp;|&nbsp; {rupt_str}'
    else:
        quadro_html = '<span style="color:#999">—</span>'

    # Falaê
    if google or ifood:
        g_str = f'⭐ {google["grade"]:.1f} ({google["total"]})' if google.get('grade') else '—'
        i_str = f'⭐ {ifood["grade"]:.1f} ({ifood["total"]})' if ifood.get('grade') else '—'
        dia_parts = []
        for plat, plabel in [('google','Google'),('ifood','iFood')]:
            s = rd.get(plat)
            if s and s.get('total'):
                txt = f'+{s["total"]} {plabel} hoje'
                if s.get('baixas'):
                    txt += f' ⚠️ {s["baixas"]} abaixo de 3★'
                dia_parts.append(txt)
        dia_html = f'<div style="color:#e67e22;font-size:0.85em;margin-top:4px">↳ {" | ".join(dia_parts)}</div>' if dia_parts else ''
        falae_html = f'Google {g_str} &nbsp;|&nbsp; iFood {i_str}{dia_html}'
    else:
        falae_html = '<span style="color:#999">—</span>'

    # Diárias
    if diarias:
        pct_num = None
        try:
            pct_num = float(diarias['pct'].replace('%','').replace(',','.'))
        except: pass
        cd = cor_pct(pct_num)
        diarias_html = f'R$ {diarias["acumulado"]} / meta R$ {diarias.get("meta","—")} &nbsp;{badge(cd, diarias.get("pct","—"))}'
    else:
        diarias_html = '<span style="color:#999">—</span>'

    # Maturidade
    score = mat.get('score')
    if score is not None:
        cm = cor_mat(score)
        q_t = mat.get('quadro_turnos', 0)
        r_t = mat.get('relatorio_turnos', 0)
        ck_e = mat.get('checklist_executado', 0)
        ck_esp = mat.get('checklist_esperado', 0)
        parcial = ' <span style="color:#e67e22;font-size:0.8em">parcial</span>' if not mat.get('tem_checklist') else ''
        ck_str = f'ck {ck_e}/{ck_esp}' if mat.get('tem_checklist') else 'ck —'
        mat_html = f'{badge(cm, f"{score}/10")} {parcial} &nbsp; <span style="color:#666;font-size:0.85em">quadro {q_t}/2 | turno {r_t}/2 | {ck_str}</span>'
    else:
        mat_html = '<span style="color:#999">—</span>'

    # Cor da borda do card baseada na maturidade
    border_cores = {'green': '#52b788', 'yellow': '#ffc107', 'red': '#e74c3c', 'gray': '#ddd'}
    border_cor = border_cores.get(cor_mat(score), '#ddd')

    return f'''
    <div style="background:#fff;border-radius:12px;padding:20px;margin-bottom:16px;
                border-left:4px solid {border_cor};
                box-shadow:0 1px 4px rgba(0,0,0,0.08);">

      <div style="font-size:1.1em;font-weight:700;color:#1a1a2e;margin-bottom:14px;">
        🏠 {label.upper()}
      </div>

      <table style="width:100%;border-collapse:collapse;">
        <tr>
          <td style="padding:6px 0;vertical-align:top;width:120px;color:#888;font-size:0.85em;font-weight:600;text-transform:uppercase;letter-spacing:0.5px;">Faturamento</td>
          <td style="padding:6px 0;vertical-align:top;">💰 {fat_html}</td>
        </tr>
        <tr style="border-top:1px solid #f0f0f0;">
          <td style="padding:6px 0;vertical-align:top;color:#888;font-size:0.85em;font-weight:600;text-transform:uppercase;letter-spacing:0.5px;">Diárias</td>
          <td style="padding:6px 0;vertical-align:top;">📊 {diarias_html}</td>
        </tr>
        <tr style="border-top:1px solid #f0f0f0;">
          <td style="padding:6px 0;vertical-align:top;color:#888;font-size:0.85em;font-weight:600;text-transform:uppercase;letter-spacing:0.5px;">Rel. Turno</td>
          <td style="padding:6px 0;vertical-align:top;">📋 {rel_html}</td>
        </tr>
        <tr style="border-top:1px solid #f0f0f0;">
          <td style="padding:6px 0;vertical-align:top;color:#888;font-size:0.85em;font-weight:600;text-transform:uppercase;letter-spacing:0.5px;">Quadro Op.</td>
          <td style="padding:6px 0;vertical-align:top;">👥 {quadro_html}</td>
        </tr>
        <tr style="border-top:1px solid #f0f0f0;">
          <td style="padding:6px 0;vertical-align:top;color:#888;font-size:0.85em;font-weight:600;text-transform:uppercase;letter-spacing:0.5px;">Reputação</td>
          <td style="padding:6px 0;vertical-align:top;">⭐ {falae_html}</td>
        </tr>
        <tr style="border-top:1px solid #f0f0f0;">
          <td style="padding:6px 0;vertical-align:top;color:#888;font-size:0.85em;font-weight:600;text-transform:uppercase;letter-spacing:0.5px;">Maturidade</td>
          <td style="padding:6px 0;vertical-align:top;">🎯 {mat_html}</td>
        </tr>
      </table>
    </div>'''

def semana_de(data_str):
    dt = date.fromisoformat(data_str)
    segunda = dt - timedelta(days=dt.weekday())
    return segunda, segunda + timedelta(days=6)

def agregar(registros):
    por_unidade = {}
    for h in registros:
        lid = h['unidade_id']
        if lid not in por_unidade:
            por_unidade[lid] = {'dias': 0, 'faturamento': 0, 'meta': 0,
                                'scores': [], 'quadro': 0, 'relatorio': 0,
                                'ck_exec': 0, 'ck_esp': 0}
        u = por_unidade[lid]
        u['dias'] += 1
        if h.get('faturamento'): u['faturamento'] += h['faturamento']
        if h.get('meta'):        u['meta']        += h['meta']
        if h.get('maturidade_score') is not None:
            u['scores'].append(h['maturidade_score'])
        u['quadro']    += h.get('quadro_turnos', 0)
        u['relatorio'] += h.get('relatorio_turnos', 0)
        u['ck_exec']   += h.get('checklist_executado', 0)
        u['ck_esp']    += h.get('checklist_esperado', 0)
    return por_unidade

def linhas_unidades(por_unidade, lojas_cache):
    out = ''
    for lid, label in LOJAS:
        u = por_unidade.get(lid)
        if not u or (not u['faturamento'] and not u['scores']): continue
        fat, meta = u['faturamento'], u['meta']
        scores = u['scores']
        mat_med = round(sum(scores)/len(scores), 1) if scores else None
        mat_b = badge(cor_mat(mat_med), f'{mat_med}/10') if mat_med is not None else '<span style="color:#999">—</span>'
        dias = u['dias']
        ops_str = f'<span style="font-size:0.78em;color:#777">quadro {u["quadro"]}/{dias*2} · turno {u["relatorio"]}/{dias*2} · ck {u["ck_exec"]}/{u["ck_esp"]}</span>'
        # Faturamento — valor principal e detalhe separados
        if fat and meta and meta > 0:
            pct = round(fat / meta * 100)
            fat_main   = f'R$ {fat:,.0f}'
            fat_detail = f'<span style="color:#888;font-size:0.78em">/ R$ {meta:,.0f} &nbsp;{badge(cor_pct(pct), f"{pct}%")}</span>'
        elif fat:
            fat_main   = f'R$ {fat:,.0f}'
            fat_detail = ''
        else:
            fat_main   = '<span style="color:#bbb">—</span>'
            fat_detail = ''

        # Reputação digital com toggle de avaliações baixas
        lc  = lojas_cache.get(lid, {})
        g   = lc.get('google') or {}
        i   = lc.get('ifood')  or {}
        rd  = lc.get('reviews_dia') or {}
        uid = lid.replace('_', '')
        rep_html = ''
        for plat, dados, label_p in [('google', g, 'G'), ('ifood', i, 'iF')]:
            if not dados.get('grade'): continue
            grade  = dados['grade']
            baixas = (rd.get(plat) or {}).get('baixas', 0)
            cor_g  = '#c0392b' if grade < 4 else '#444'
            tid    = f'rep_{uid}_{plat}'
            detail = ''
            textos = (rd.get(plat) or {}).get('textos', [])
            if baixas:
                linhas = ''
                for t in textos[:5]:
                    estrelas = '⭐' * int(t.get('nota', 1))
                    cliente  = t.get('cliente', 'Anônimo')
                    texto    = t.get('texto', '').strip()
                    linhas  += f'<div style="margin-top:5px;padding-top:5px;border-top:1px solid #f5c6c6;">'
                    linhas  += f'<span style="font-weight:600">{estrelas} {cliente}</span>'
                    if texto:
                        linhas += f'<br><span style="color:#555">{texto[:120]}</span>'
                    linhas  += '</div>'
                detail = (f'<div id="{tid}" style="display:none;margin-top:4px;'
                          f'background:#fdecea;border-radius:6px;padding:6px 8px;'
                          f'font-size:0.75em;color:#c0392b;">'
                          f'⚠️ {baixas} avaliação{"ões" if baixas>1 else ""} abaixo de 3★ hoje'
                          f'{linhas}</div>')
                onclick = f"onclick=\"var e=document.getElementById('{tid}');e.style.display=e.style.display==='none'?'block':'none'\""
                rep_html += (f'<div style="font-size:0.82em;color:{cor_g};cursor:pointer;" {onclick}>'
                             f'{label_p} ⭐{grade:.1f} <span style="font-size:0.8em;color:#c0392b">▼</span>'
                             f'</div>{detail}')
            else:
                rep_html += f'<div style="font-size:0.82em;color:{cor_g}">{label_p} ⭐{grade:.1f}</div>'
        if not rep_html:
            rep_html = '<div style="color:#bbb;font-size:0.82em">—</div>'

        out += f'''
        <div style="padding:10px 0;border-top:1px solid #f0f0f0;">
          <div style="font-weight:700;font-size:0.93em;margin-bottom:8px;">{label}</div>
          <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:4px;margin-bottom:6px;">
            <div>
              <div style="font-size:0.7em;color:#888;font-weight:600;text-transform:uppercase;letter-spacing:0.4px;margin-bottom:2px;">Faturamento</div>
              <div style="font-size:0.88em;font-weight:600;">{fat_main}</div>
              <div>{fat_detail}</div>
            </div>
            <div style="text-align:center;">
              <div style="font-size:0.7em;color:#888;font-weight:600;text-transform:uppercase;letter-spacing:0.4px;margin-bottom:4px;">Maturidade</div>
              {mat_b}
              <div style="margin-top:5px;">{ops_str}</div>
            </div>
            <div style="text-align:right;">
              <div style="font-size:0.7em;color:#888;font-weight:600;text-transform:uppercase;letter-spacing:0.4px;margin-bottom:2px;">Reputação</div>
              {rep_html}
            </div>
          </div>
        </div>'''
    return out

def card_historico(data_ref, lojas_cache):
    hist_path = os.path.join(DIR, 'HISTORICO_DIARIO.json')
    if not os.path.exists(hist_path):
        return ''
    with open(hist_path, encoding='utf-8') as f:
        historico = json.load(f)
    if not historico:
        return ''

    # ── Semanas disponíveis ──────────────────────────────────────────────────
    semanas_set = {}
    for h in historico:
        seg, dom = semana_de(h['data'])
        key = seg.isoformat()
        if key not in semanas_set:
            semanas_set[key] = dom
    semanas = sorted(semanas_set.items(), reverse=True)  # [(seg_iso, dom), ...]

    seg_atual, dom_atual = semana_de(data_ref)
    seg_atual_iso = seg_atual.isoformat()

    # ── Meses disponíveis ────────────────────────────────────────────────────
    meses_set = sorted(set(h['data'][:7] for h in historico), reverse=True)

    # ── Gera HTML de cada semana ─────────────────────────────────────────────
    semanas_html = {}
    for seg_iso, dom in semanas:
        dom_iso = dom.isoformat()
        regs = [h for h in historico if seg_iso <= h['data'] <= dom_iso]
        pu = agregar(regs)
        seg_d = date.fromisoformat(seg_iso)
        titulo = f"SEMANA {seg_d.strftime('%d/%m')} – {dom.strftime('%d/%m')}"
        corpo = linhas_unidades(pu, lojas_cache)
        semanas_html[seg_iso] = f'<div style="font-weight:700;font-size:0.95em;margin-bottom:8px;">📅 {titulo}</div>{corpo}'

    # ── Gera HTML de cada mês ────────────────────────────────────────────────
    MESES_PT = {'01':'Jan','02':'Fev','03':'Mar','04':'Abr','05':'Mai','06':'Jun',
                '07':'Jul','08':'Ago','09':'Set','10':'Out','11':'Nov','12':'Dez'}
    meses_html = {}
    for mes_iso in meses_set:
        regs = [h for h in historico if h['data'].startswith(mes_iso)]
        pu = agregar(regs)
        ano, mm = mes_iso.split('-')
        titulo = f"{MESES_PT.get(mm, mm)} {ano}"
        corpo = linhas_unidades(pu, lojas_cache)
        meses_html[mes_iso] = f'<div style="font-weight:700;font-size:0.95em;margin-bottom:8px;">📆 {titulo}</div>{corpo}'

    # ── Mapeia mês → semanas disponíveis ────────────────────────────────────
    mes_semanas = {}  # mes_iso → [(seg_iso, label), ...]
    for seg_iso, dom in semanas:
        mes_iso = seg_iso[:7]
        label = f'{date.fromisoformat(seg_iso).strftime("%d/%m")} – {dom.strftime("%d/%m")}'
        mes_semanas.setdefault(mes_iso, []).append((seg_iso, label))

    # mês atual
    mes_atual = data_ref[:7]
    if mes_atual not in mes_semanas:
        mes_atual = meses_set[0] if meses_set else mes_atual

    opts_meses = ''.join(
        f'<option value="{m}" {"selected" if m == mes_atual else ""}>'
        f'{MESES_PT.get(m.split("-")[1], "")} {m.split("-")[0]}'
        f'</option>'
        for m in meses_set
    )

    semanas_js   = json.dumps(semanas_html,  ensure_ascii=False)
    mes_semanas_js = json.dumps({
        m: [(s, l) for s, l in sems]
        for m, sems in mes_semanas.items()
    }, ensure_ascii=False)
    meses_js     = json.dumps(meses_html,    ensure_ascii=False)

    return f'''
<div style="background:#fff;border-radius:12px;padding:16px 20px;margin-bottom:16px;box-shadow:0 1px 4px rgba(0,0,0,0.08);">

  <!-- Seletor de mês -->
  <select id="sel-mes" onchange="onMesChange(this.value)"
    style="width:100%;padding:9px 12px;border-radius:8px;border:1px solid #ddd;font-size:0.95em;font-weight:600;margin-bottom:12px;color:#1a1a2e;">
    {opts_meses}
  </select>

  <!-- Seletor de semana (dentro do mês) -->
  <select id="sel-semana" onchange="renderSemana(this.value)"
    style="width:100%;padding:8px 10px;border-radius:8px;border:1px solid #ddd;font-size:0.88em;color:#444;margin-bottom:14px;">
  </select>

  <!-- Conteúdo da semana selecionada -->
  <div id="semana-body"></div>

</div>

<script>
const SEMANAS     = {semanas_js};
const MES_SEMANAS = {mes_semanas_js};
const MESES_HTML  = {meses_js};

function onMesChange(mes) {{
  const sems = MES_SEMANAS[mes] || [];
  const sel = document.getElementById('sel-semana');
  sel.innerHTML = sems.map(([s,l]) => `<option value="${{s}}">${{l}}</option>`).join('');
  if (sems.length) renderSemana(sems[0][0]);
  else document.getElementById('semana-body').innerHTML = '<p style="color:#999">Sem dados.</p>';
}}

function renderSemana(v) {{
  document.getElementById('semana-body').innerHTML = SEMANAS[v] || '<p style="color:#999">Sem dados.</p>';
  document.getElementById('sel-semana').value = v;
}}

function navSemana(dir) {{
  const sel = document.getElementById('sel-semana');
  const opts = Array.from(sel.options);
  const idx = opts.findIndex(o => o.value === sel.value);
  const next = idx + dir;
  if (next >= 0 && next < opts.length) renderSemana(opts[next].value);
}}

// inicializa com mês atual
onMesChange('{mes_atual}');
// tenta selecionar a semana atual dentro do mês
(function() {{
  const sel = document.getElementById('sel-semana');
  const opts = Array.from(sel.options);
  const cur = opts.find(o => o.value === '{seg_atual_iso}');
  if (cur) renderSemana(cur.value);
}})();
</script>'''

def gerar_html(cache):
    DATA_DT = date.fromisoformat(cache['data'])
    data_fmt = DATA_DT.strftime('%d/%m/%Y')
    gerado  = cache.get('gerado_em', '—')

    # Resumo semanal + histórico
    semana_html = card_historico(cache['data'], cache.get('lojas', {}))

    # Cards das lojas
    cards = ''
    for lid, label in LOJAS:
        loja = cache['lojas'].get(lid, {})
        cards += card_loja(lid, label, loja)

    # VMarket
    vm = cache.get('vmarket', {})
    semana = cache.get('semana_inicio', '')
    sem_fmt = f'{semana[8:10]}/{semana[5:7]}' if semana else '—'
    # VMarket — só mostra empresas com dados reais (total > 0)
    vm_ativas = {emp: d for emp, d in vm.items() if (d.get('total') or 0) > 0}
    if vm_ativas:
        total_g = sum((d.get('total') or 0) for d in vm_ativas.values())
        vm_rows = ''
        for emp, d in vm_ativas.items():
            tot = d.get('total') or 0
            ped = d.get('pedidos') or 0
            vm_rows += f'<tr><td style="padding:6px 12px;text-transform:capitalize">{emp}</td><td style="padding:6px 12px;text-align:right">R$ {tot:,.2f}</td><td style="padding:6px 12px;text-align:right;color:#888">{ped} pedidos</td></tr>'
        vm_rows += f'<tr style="border-top:2px solid #ddd;font-weight:700"><td style="padding:8px 12px">TOTAL GRUPO</td><td style="padding:8px 12px;text-align:right">R$ {total_g:,.2f}</td><td></td></tr>'
        vm_html = f'''
        <table style="width:100%;border-collapse:collapse;font-size:0.9em;">
          {vm_rows}
        </table>'''
    else:
        vm_html = '<p style="color:#999">— sem dados (JWT expirado)</p>'

    erros_html = ''  # erros técnicos não aparecem no HTML público

    return f'''<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Report Matinal — {data_fmt}</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: #f4f6f9;
      color: #1a1a2e;
      padding: 16px;
      max-width: 680px;
      margin: 0 auto;
    }}
    h1 {{
      font-size: 1.3em;
      font-weight: 700;
      color: #1a1a2e;
      margin-bottom: 4px;
    }}
    .subtitle {{
      color: #888;
      font-size: 0.85em;
      margin-bottom: 20px;
    }}
    .section-title {{
      font-size: 0.8em;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 1px;
      color: #888;
      margin: 24px 0 10px;
    }}
    .vmarket-card {{
      background: #fff;
      border-radius: 12px;
      padding: 20px;
      box-shadow: 0 1px 4px rgba(0,0,0,0.08);
    }}
    .footer {{
      text-align: center;
      color: #bbb;
      font-size: 0.75em;
      margin-top: 24px;
      padding-bottom: 24px;
    }}
  </style>
</head>
<body>

  <h1>☀️ Report Matinal</h1>
  <div class="subtitle">{data_fmt} &nbsp;·&nbsp; gerado em {gerado}</div>

  <div class="section-title">📅 Resumo Semanal</div>
  {semana_html}

  <div class="section-title">Unidades — Ontem</div>
  {cards}

  <div class="footer">Grupo Cantucci · {data_fmt}</div>

</body>
</html>'''

# ─── Main ─────────────────────────────────────────────────────────────────────
cache = load_cache()
if not cache:
    print('DAILY_CACHE.json não encontrado — rode: py -3 daily_sync.py')
    sys.exit(1)

html = gerar_html(cache)
out_path = os.path.join(DIR, 'DAILY_REPORT.html')
with open(out_path, 'w', encoding='utf-8') as f:
    f.write(html)

print(f'✅ DAILY_REPORT.html gerado — {cache["data"]}')
