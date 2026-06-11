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
./run_opentes.sh <cenario>     # star | ieee13 | controller-demo | integrated
```

| Cenário | O que faz | Resultado em |
|---------|-----------|--------------|
| `star`            | Comunicação pura: PADE ↔ OMNeT++ (50 agentes em estrela) | `output/star/` |
| `ieee13`          | Rede elétrica IEEE 13 + 5 PVs + inversores (só elétrico)  | `output/ieee13/` |
| `controller-demo` | Agente PADE controlando uma bateria (sem comunicação)    | `output/controller_demo/` |
| `integrated`      | **Acoplamento causal completo** dos 4 containers          | `output/integrated/` |

### O cenário integrado (`integrated`) — acoplamento causal Volt/Var

Evolução do `mosaik-opentes/scenarios/first.py` (que já unia PADE+OMNeT+++Mosaik),
agora fechando o laço com o OpenDSS. **Sem bateria**: o atuador é o **inversor
do PVSystem PV2** (Bus 632), com controle **Volt/Var**:

```
OpenDSS resolve V  ──►  AgenteA (medidor) lê a tensão do Bus-632
                              │  publica mensagem FIPA-ACL
                              ▼
                        OMNeT++  (latência / jitter / perda de pacotes)
                              │  tensão chega ATRASADA
                              ▼
                        AgenteB (controlador Volt/Var):
                          P (ativa)   = solar disponível
                          Q (reativa) = f(tensão),  S = √(P²+Q²) ≤ kVA
                              │
                              ▼
                        PVSystem.PV2 (P_des, Q_des) ──► OpenDSS muda a injeção
                              │
                              └────► (próximo passo: nova V) — laço fecha
```

O cenário roda **duas vezes** e compara — **sem** controle (baseline) e **com**
controle (Volt/Var) — com **0% de perda** (ideal para isolar o efeito do
controle; ajuste `omnetpp.ini` para estudar a perda). Registros em
`output/integrated/`:

- `result_baseline.csv` / `result_volt_var.csv` — trajetórias elétricas (V de
  632, P_ref e Q_ref do agente, injeção P_meas/Q_meas no PV2).
- `comm_trace_baseline.csv` / `comm_trace_volt_var.csv` — rastro das mensagens
  pela rede OMNeT++ (FIPA com a tensão + telemetria: pacotes, latência, jitter).
- `comparacao_volt_var.png` — gráfico comparativo (tensão e reativo).

Resultado: o Volt/Var leva a tensão média do Bus 632 para mais perto do nominal
(1,0089 → 1,0011 pu) injetando até 820 kvar. Detalhes em
[`docs/INTEGRACAO.md`](docs/INTEGRACAO.md#resultados).

## Como rodar

Pré-requisito (uma vez): `docker compose build`.

```bash
# acoplamento causal completo (os 4 containers)
./run_opentes.sh integrated

# rede elétrica IEEE 13 isolada + dashboard
./run_opentes.sh ieee13
docker compose run --rm --no-deps mosaik python plot_ieee13.py   # output/ieee13/ieee13_dashboard.png

# comunicação pura (gera output/star/grafico_trafego.png)
./run_opentes.sh star

# controlador de bateria isolado
./run_opentes.sh controller-demo
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
├── controller_demo/  result_battery_controller_demo.csv
└── integrated/       result_baseline.csv | result_volt_var.csv
                      comm_trace_baseline.csv | comm_trace_volt_var.csv
                      comparacao_volt_var.png
```

## Coerência dos resultados

O IEEE 13 reproduz **exatamente** os valores do cenário de referência do TSRE
(Paulo Victor, branch `paulo-victor`): geração `P_dc` ≈ 3024,6 kW, `P_ac` ≈
2854,2 kW e `P_meas` ≈ 1902,7 kW de pico. As tensões ficam na faixa esperada do
IEEE 13 desbalanceado (barra 650/fonte em 1,0 pu; barras trifásicas 0,91–1,05 pu;
fases inexistentes de trechos monofásicos em 0,0).

Mais contexto técnico em `docs/INTEGRACAO.md` e no histórico de
`docs/ALTERACOES_INTEGRACAO.txt`.
