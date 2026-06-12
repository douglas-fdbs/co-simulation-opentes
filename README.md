# OpenTES — Co-simulação multidomínio (PADE + OMNeT++ + Mosaik + OpenDSS)

Repositório agregador da integração dos times **TSCC** (comunicação/co-simulação),
**TTESO** (agentes PADE) e **TSRE** (rede elétrica), tendo o **IEEE 13 Barras**
como benchmark. O Mosaik é o orquestrador temporal ("maestro"); toda a informação
elétrica trafega pela rede de comunicação simulada no OMNeT++, de modo que
latência, jitter e perda de pacotes sejam contabilizados.

## Estrutura — 4 containers funcionais

| Container | Pasta | Papel |
|-----------|-------|-------|
| `comm`   | `simulators_teams/comm-opentes`   | Rede de comunicação (OMNeT++ + bridge ZMQ) |
| `pade`   | `simulators_teams/pade-opentes`   | Agentes PADE (Python 3.12) |
| `mosaik` | `simulators_teams/mosaik-opentes` | Orquestrador Mosaik + cenários + collectors |
| `grid`   | `simulators_teams/grid-opentes`   | Rede elétrica IEEE 13 (OpenDSS via `py-dss-interface`) |

## Cenários disponíveis

A forma recomendada de executar é pelo script `run_opentes.sh`, que faz a
limpeza completa do Docker antes/depois (evita o erro `network ... not found`
causado por containers de profile que o `down` simples não remove):

```bash
./run_opentes.sh <cenario>     # integrated | star | ieee13
```

| Cenário | O que faz | Resultado em |
|---------|-----------|--------------|
| `integrated`      | **Co-simulação completa** dos 4 containers (Volt/Var causal) | `output/integrated/` |
| `star`            | Comunicação pura: PADE ↔ OMNeT++ (50 agentes em estrela) — teste isolado | `output/star/` |
| `ieee13`          | Rede elétrica IEEE 13 + 5 PVs + inversores (só elétrico) — teste isolado | `output/ieee13/` |

O `integrated` é **a** simulação (a aplicação); `star` e `ieee13` são bancadas
de teste isoladas de cada bloco.

### O cenário integrado (`integrated`) — acoplamento causal Volt/Var

Evolução do `mosaik-opentes/scenarios/first.py` (que já unia PADE+OMNeT+++Mosaik),
agora fechando o laço com o OpenDSS. **PV System**: reproduz o estado do TSRE
(5 PVs injetando), mas **co-simulado e controlado** — cada um dos **5 inversores**
tem um par de agentes (medidor + controlador Volt/Var) e a tensão da sua barra
trafega pela rede OMNeT++:

```
OpenDSS resolve V  ──►  AgenteA_i (medidor) lê a tensão da barra do PV_i
                              │  publica mensagem FIPA-ACL (marcada com a barra)
                              ▼
                        OMNeT++  (latência / jitter / perda de pacotes)
                              │  tensão chega ATRASADA
                              ▼
                        AgenteB_i (controlador Volt/Var):
                          P (ativa)   = solar disponível
                          Q (reativa) = f(tensão),  S = √(P²+Q²) ≤ kVA
                              │
                              ▼
                        PVSystem.PV_i (P_des, Q_des) ──► OpenDSS muda a injeção
                              │
                              └────► (próximo passo: nova V) — laço fecha   (i = 1..5)
```

O cenário roda **duas vezes** e compara — **sem** controle (baseline) e **com**
controle (Volt/Var). A perda de pacotes é **parâmetro de modelo da rede**
(`drop_probability` no `omnetpp.ini`, herdado do TSCC = 15%) com **semente fixa**.
Registros em `output/integrated/`:

- `result_baseline.csv` / `result_volt_var.csv` — trajetórias elétricas (tensão
  de todas as barras, P_ref/Q_ref dos 5 controladores, P_meas/Q_meas dos 5 PVs).
- `comm_trace_baseline.csv` / `comm_trace_volt_var.csv` — rastro das mensagens
  pela rede OMNeT++ (FIPA com a tensão + telemetria: pacotes, latência, jitter).
- `dashboard_integrated.png` — painel de 8 quadros unindo os dois domínios:
  irradiância (5 PVs), temperatura, geração FV agregada, tensões das 13 barras,
  integridade de pacotes (pizza entregues×dropados), latência exata, jitter
  distribuído e o efeito do Volt/Var nas 5 barras PV.

A tabela completa do que cada arquivo apresenta está em
[`docs/INTEGRACAO.md`](docs/INTEGRACAO.md#resultados).

Resultado: o Volt/Var dá **suporte de tensão** — eleva as barras subtensionadas
(Bus 652: mínima 0,920 → 0,938 pu) e reduz o desvio em até 19% (média −10%), de
forma estável, com perda realista de **18,6%**. Achado importante: ganho
agressivo + atraso/perda da rede **desestabiliza** o controle distribuído (motiva
estudar o impacto da comunicação). Comparativo e
observações em [`docs/INTEGRACAO.md`](docs/INTEGRACAO.md#resultados).

## Como rodar

Pré-requisito (uma vez): `docker compose build`.

```bash
# co-simulação completa (4 containers, Volt/Var): roda baseline + Volt/Var
./run_opentes.sh integrated
docker compose run --rm --no-deps -e MOSAIK_OUTPUT_DIR=/app/output/integrated \
  mosaik python plot_integrated.py     # output/integrated/dashboard_integrated.png

# rede elétrica IEEE 13 isolada + dashboard
./run_opentes.sh ieee13
docker compose run --rm --no-deps mosaik python plot_ieee13.py   # output/ieee13/ieee13_dashboard.png

# comunicação pura (gera output/star/grafico_trafego.png)
./run_opentes.sh star
```

> **Atenção operacional**: os simuladores `--remote` do grid aceitam uma única
> conexão Mosaik e encerram após. Por isso o `run_opentes.sh` sempre sobe
> containers frescos. Não sondar as portas `--remote` com TCP de readiness (isso
> consome a conexão e mata o simulador) — sondar apenas o `comm` (5555, ZMQ).

## Onde observar os resultados

Tudo é gravado em `output/`, separado por cenário:

```
output/
├── star/             results.csv  +  grafico_trafego.png
├── ieee13/           result_run_ieee13_cosim_pv_5min.csv  +  ieee13_dashboard.png
└── integrated/       result_baseline.csv | result_volt_var.csv
                      comm_trace_baseline.csv | comm_trace_volt_var.csv
                      dashboard_integrated.png
```

O **guia didático** de cada arquivo (coluna a coluna, linha a linha) e de cada
gráfico está em [`docs/RESULTADOS.md`](docs/RESULTADOS.md).

## Coerência dos resultados

O IEEE 13 reproduz **exatamente** os valores do cenário de referência do TSRE
(Paulo Victor, branch `paulo-victor`): geração `P_dc` ≈ 3024,6 kW, `P_ac` ≈
2854,2 kW e `P_meas` ≈ 1902,7 kW de pico. As tensões ficam na faixa esperada do
IEEE 13 desbalanceado (barra 650/fonte em 1,0 pu; barras trifásicas 0,91–1,05 pu;
fases inexistentes de trechos monofásicos em 0,0).

Documentação: [`docs/INTEGRACAO.md`](docs/INTEGRACAO.md) (visão geral, decisões e
resultados), [`docs/RESULTADOS.md`](docs/RESULTADOS.md) (guia da pasta `output/`)
e [`docs/ALTERACOES_INTEGRACAO.txt`](docs/ALTERACOES_INTEGRACAO.txt) (changelog
técnico das alterações e seus motivos).
