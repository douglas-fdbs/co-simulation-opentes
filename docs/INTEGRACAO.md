# Integração OpenTES

Este documento resume a organização inicial do repositório agregador
`co-simulation-opentes` e o estado atual da integração entre os simuladores dos
times TTESO, TSCC e TSRE.

## Objetivo

O fluxo alvo desta etapa é:

```text
PADE -> Mosaik -> OMNeT++ -> Mosaik -> PADE -> Mosaik -> OpenDSS
```

O benchmark operacional inicial é o IEEE 13 Bus. A ideia é validar primeiro a
comunicação entre domínios e, em seguida, substituir mensagens artificiais por
payloads com semântica elétrica e de controle.

## Estrutura

A integração foi reorganizada em **4 containers funcionais**, refletindo a divisão
entre domínios de simulação:

- `simulators_teams/comm-opentes`: simulação de comunicação (OMNeT++ + bridge ZMQ).
  Conteúdo migrado de `tscc-com-opentes/omnet-dir`.
- `simulators_teams/pade-opentes`: runtime PADE (Python 3.12) + agentes.
  Resultado da fusão de `tteso-tes-opentes` (lib PADE) com
  `tscc-com-opentes/pade-dir/pade_agents` (scripts dos agentes).
- `simulators_teams/mosaik-opentes`: engine Mosaik, `scenarios/` e `collectors/`.
  Concentra o cenário de comunicação (era `tscc-com-opentes/mosaik-dir`) e o
  collector elétrico do TSRE (era `tsre-der-opentes/src/simulators/collector.py`).
- `simulators_teams/grid-opentes`: rede elétrica + simuladores DER remotos.
  Equivalente ao antigo `tsre-der-opentes` do time TSRE, sem o collector (que
  migrou para `mosaik-opentes`). O nome do diretório passou a refletir o
  conteúdo (rede elétrica) em vez do nome do time.

## Decisões Técnicas

- O repositório raiz é o agregador dos componentes usados nesta etapa.
- Os `.git` internos dos repositórios importados foram removidos para que o
  agregador versione a base integrada.
- A topologia passou de **3 Dockerfiles multi-uso** para **4 Dockerfiles
  funcionais**, um por container principal (comm, pade, mosaik, tsre).
- O cenário Mosaik (`scenarios/star.py`) e os collectors (`collectors/comm_collector.py`,
  `collectors/elec_collector.py`) vivem em `mosaik-opentes`. O `comm_collector` salva
  telemetria de rede (packets, latências, jitter via `mosaik_api_v3`); o
  `elec_collector` salva dados elétricos com timestamp (`mosaik_api` legado).
- O controle de bateria foi migrado para um **agente PADE**
  (`pade-opentes/agents/controller_agent.py`, classe `BatteryControllerAgent`).
  O simulador Mosaik original (`controller_sim.py`) foi arquivado em
  `grid-opentes/src/simulators/old/`. O novo agente preserva a interface
  Mosaik com o mesmo modelo `BatteryController` (params/attrs idênticos) e
  abre caminho para coordenação distribuída via FIPA-ACL futuramente. Para
  subir o serviço opt-in: `docker compose --profile controller up pade-controller`.
- O `mosaik_driver.py` do PADE (classe `MosaikCon`) é a ponte oficial entre
  agentes PADE e Mosaik. Foi atualizado para Mosaik 3 e usado pelo `pade_star.py`.
- A versão comum de Mosaik é `3.5.0`, porque o TSRE já estava alinhado nela e o
  cenário de comunicação foi validado nessa versão.
- O `py-dss-interface>=2.3.0` é usado diretamente no Linux. A versão atual
  fornece wheels Linux, dispensando a compilação manual da engine OpenDSS.
- A porta interna `5678` do PADE é publicada como `15678` no host para evitar
  conflito com o serviço `pv-panel` do TSRE.
- Variáveis de ambiente `OMNET_HOST`, `OMNET_PORT`, `PADE_HOST`, `PADE_PORT`
  permitem ajustar destinos sem editar código nos cenários.

## Ambiente Python

Na raiz do repositório:

```bash
uv sync
```

Validação básica:

```bash
uv run python -c "import pade, mosaik, mosaik_api, mosaik_api_v3, zmq, py_dss_interface; print('ok')"
```

O OMNeT++ não é instalado no ambiente Python local; ele é tratado pelo
container do TSCC.

## Docker

Build geral:

```bash
docker compose build
```

Smoke integrado do fluxo PADE↔Mosaik↔OMNeT++:

```bash
docker compose up --abort-on-container-exit --exit-code-from mosaik mosaik
docker compose down --remove-orphans
```

Validação do cenário IEEE 13 do TSRE em container:

```bash
docker compose run --rm --no-deps opendss python -u /app/src/scenarios/opendss_scenario.py
docker compose down --remove-orphans
```

O `docker compose down` é importante porque os serviços auxiliares (`comm`,
`pade`) podem continuar vivos após o encerramento do cenário `mosaik`.

## Testes Executados (etapa anterior, em 3 Dockerfiles)

- Imports gerais do ambiente Python integrado.
- Imports dos módulos TSCC/Mosaik, TSCC/PADE e TSRE.
- `pade version`, retornando PADE `3.0`.
- OpenDSS IEEE 13 direto via `py-dss-interface`, convergindo no Linux.
- Cenário TSRE `opendss_scenario.py`, local e em container, com 144 passos de
  10 minutos.
- Probe TSCC com PADE falso e com PADE real remoto.
- Compile-test do modelo OMNeT++ com ZMQ.
- Smoke integrado TSCC com PADE, Mosaik e OMNeT++ por 20 passos e 50 periféricos.

Após a reorganização para **4 containers**, os mesmos testes precisam ser
re-validados nos novos serviços `comm`, `pade`, `mosaik` e `tsre`. Ver
`docs/ALTERACOES_INTEGRACAO.txt` seção 9 para o registro da mudança.

Artefatos como `results.csv`, `grafico_trafego.png`, `sim_exec`, `out/` e
saídas do OpenDSS são produtos de simulação e estão no `.gitignore`.

## Resultados

### Co-simulação integrada (cenário `integrated`, IEEE 13 Barras)

A co-simulação completa (`./run_opentes.sh integrated`) fecha o laço causal
sobre o IEEE 13 Barras, sem bateria — o atuador é o **inversor do PVSystem PV2**
(Barramento 632), com **controle Volt/Var** feito por um agente PADE:

```
OpenDSS Bus-632.V → AgenteA (mede) → OMNeT++ (atraso/jitter) → AgenteB (Volt/Var)
                                                                      │ P=solar, Q=f(V)
OpenDSS ← PVSystem PV2 (P_des, Q_des) ←───────────────────────────────┘
```

- **P (ativa)** = potência solar disponível (cadeia irradiância → PV panel).
- **Q (reativa)** = função da tensão recebida **pela rede de comunicação**,
  respeitando `S = √(P² + Q²) ≤ kVA` do inversor (PV2: 3000 kVA).
- A tensão medida trafega pelo OMNeT++; latência/jitter/perda são contabilizados.

O experimento roda **duas vezes** e compara — sem controle (baseline) e com
controle (Volt/Var) — com **0% de perda de pacotes** (`drop_probability = 0.0`
no `omnetpp.ini`, condição ideal para isolar o efeito do controle).

**Telemetria da rede de comunicação (OMNeT++), por execução:**

| Métrica | Valor |
|---|---|
| Pacotes enviados | 288 (1 por passo, 1 dia a 5 min) |
| Pacotes recebidos | 288 |
| Pacotes perdidos | 0 (0%) |

**Efeito do controle Volt/Var na tensão do Barramento 632:**

| Métrica (tensão pu) | Sem controle | Com Volt/Var |
|---|---:|---:|
| Tensão média | 1,0089 | **1,0011** (mais perto do nominal) |
| Desvio-padrão | 0,0096 | **0,0088** (−8%) |
| Reativo Q médio | 0 kvar | 399 kvar |
| Reativo Q máximo | 0 kvar | 820 kvar |

O controlador foi validado pelos próprios logs do agente (sinal correto):
`V = 1,0184 → Q = −277 kvar` (tensão alta ⇒ absorve reativo) e
`V = 0,9850 → Q = +reativo` (tensão baixa ⇒ injeta reativo). À noite, com a
solar nula, o inversor atua como **STATCOM** (só reativo), trazendo a tensão
levemente alta de volta ao nominal. A co-simulação captura o fato de o agente
agir sobre a tensão **atrasada pela rede** — fenômeno central do benchmark.

**O que cada arquivo de `output/integrated/` apresenta** (é o que se leva para
analisar a simulação):

| Arquivo | O que contém | Para quê |
|---|---|---|
| `result_baseline.csv` | Trajetórias elétricas **sem** controle: tensão das 3 fases do Bus 632, `P_ref` (=solar) e `Q_ref` (=0) do agente, `P_meas`/`Q_meas` injetados no PV2, `P_dc` do painel. | Linha de base (inversor só injeta a solar). |
| `result_volt_var.csv` | As mesmas grandezas **com** controle Volt/Var (agora `Q_ref` ≠ 0). | Caso controlado. |
| `comm_trace_baseline.csv` | Rastro da **rede de comunicação** na execução baseline: a mensagem FIPA com a tensão (`val_out`) e a telemetria do OMNeT++ (`packets_sent/received/dropped`, `latencies_out`, `jitters_out`, `packet_sizes_out`). | Comprova que a tensão trafegou pela rede e mede o atraso. |
| `comm_trace_volt_var.csv` | Idem para a execução com Volt/Var. | Mesma telemetria, caso controlado. |
| `dashboard_integrated.png` | Painel visual: (1) tensão baseline×Volt/Var, (2) P ativa e Q reativa do inversor PV2, (3) latência/jitter da comunicação. | Resumo da co-simulação para apresentação. |

Cada linha dos `result_*.csv` é um passo de 5 min (288 = 1 dia); cada linha dos
`comm_trace_*.csv` é a telemetria daquele passo. As colunas com `Bus-632` são as
tensões por fase (as fases inexistentes do trecho ficam ~0 e são ignoradas).

Gere o painel após rodar o cenário:

```bash
docker compose run --rm --no-deps -e MOSAIK_OUTPUT_DIR=/app/output/integrated \
  mosaik python plot_integrated.py     # -> output/integrated/dashboard_integrated.png
```

### Validação do bloco elétrico (cenário `ieee13`, isolado)

O cenário elétrico puro (`./run_opentes.sh ieee13`, IEEE 13 + 5 PVs) reproduz
**exatamente** os valores do trabalho do TSRE (Paulo Victor, branch
`paulo-victor`), confirmando que a integração não alterou a física:

| Grandeza (máximo no dia) | Nosso | Referência TSRE |
|---|---:|---:|
| P_dc (painel) | 3024,6 kW | 3024,6 kW |
| P_ac (inversor) | 2854,2 kW | 2854,2 kW |
| P_meas (injeção OpenDSS) | 1902,7 kW | 1902,7 kW |

Tensões do IEEE 13 coerentes: barra 650 (fonte) = 1,000 pu; barras trifásicas
0,91–1,05 pu; fases de trechos monofásicos (ex.: 611 A/B) em 0,0 (corretas).

### Como reproduzir

```bash
./run_opentes.sh integrated   # roda baseline + Volt/Var; saídas em output/integrated/
./run_opentes.sh ieee13       # bloco elétrico isolado (validação vs Paulo Victor)
```

Para estudar o impacto da **perda de pacotes** no controle, aumente
`**.node_0.drop_probability` no `simulators_teams/comm-opentes/omnetpp.ini`
(ex.: `0.15` = 15%) e compare as tensões resultantes.
