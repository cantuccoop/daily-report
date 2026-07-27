Mostra o report semanal consolidado por unidade: faturamento vs meta, maturidade operacional (quadro/turno/checklist), reputação (Falaê), CMC da semana, CMV do mês, delivery, descontos, upsell/alcoólica, TMA e projeção do mês (tudo do Cantucci OS) — somado/mediado na semana (segunda a domingo).

**Argumento opcional:** data dentro da semana alvo (padrão: semana passada).
- `/weekly`
- `/weekly 2026-07-20`

## Como funciona

Lê o `WEEKLY_CACHE.json` gerado pelo `weekly_sync.py`, que roda toda segunda de manhã via GitHub Actions
(antes do envio das 10h). Faturamento/meta/maturidade/quadro/relatório/checklist vêm do
`HISTORICO_DIARIO.json` já coletado dia a dia pelo `daily_sync.py`; reputação (Falaê) é buscada direto
na API para a semana inteira; CMC da semana e CMV do mês corrente vêm do painel CMC/CMV do Grupo 3V
(`cmc_cmv_mapear.py`, via `CMC_CMV_DADOS.json`) — o painel não calcula CMV por semana, só por mês.
Delivery, descontos, upsell, bebida alcoólica, TMA (cozinha/bar) e projeção do mês vêm direto da API
do Cantucci OS (`cantucci_os_semanal.py`, via `CANTUCCI_OS_SEMANAL.json`) — projeção também é só mensal,
a API não calcula projeção por semana.

## Passos

1. Execute:
   ```
   py -3 weekly_report.py [YYYY-MM-DD]
   ```

2. Se o cache estiver desatualizado ou ausente, rode a sync manualmente:
   ```
   py -3 cmc_cmv_mapear.py [YYYY-MM-DD]
   py -3 cantucci_os_semanal.py [YYYY-MM-DD]
   py -3 weekly_sync.py [YYYY-MM-DD]
   ```

3. Apresente o output diretamente, sem reformatar.

## Arquitetura
- `cmc_cmv_mapear.py` — login no painel CMC/CMV (Streamlit, Grupo 3V) e salva `CMC_CMV_DADOS.json`
- `cantucci_os_semanal.py` — coleta delivery/descontos/upsell/alcoólica/TMA/projeção via API do Cantucci OS e salva `CANTUCCI_OS_SEMANAL.json`
- `weekly_sync.py` — agrega a semana (segunda a domingo) e salva `WEEKLY_CACHE.json`
- `weekly_report.py` — lê o cache e imprime instantâneo
- `WEEKLY_CACHE.json` — cache da semana
- GitHub Actions: `.github/workflows/weekly_sync.yml` — segunda-feira de manhã
- Rotina "Relatório Semanal - Envio 10h" — toda segunda às 10h
