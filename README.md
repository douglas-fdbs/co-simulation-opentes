# OpenTES Co-simulation Integration

Este repositório passa a ser o agregador dos componentes usados na etapa
inicial de integração do OpenTES.

## Estrutura

A integração é organizada em **4 containers funcionais**:

- `simulators_teams/comm-opentes`: simulador de comunicação OMNeT++ + bridge ZMQ.
- `simulators_teams/pade-opentes`: runtime PADE (Python 3.12) + agentes.
- `simulators_teams/mosaik-opentes`: engine Mosaik, cenários e collectors (telemetria de rede + dados elétricos).
- `simulators_teams/grid-opentes`: rede elétrica + DERs (OpenDSS via `py-dss-interface`).
- `examples/mosaik-docker-example`: conteúdo original do `co-simulation-opentes`, mantido como referência de dockerização simples.
- `examples/tscc-mosaik-compat`: probe de compatibilidade do adaptador Mosaik (comm + collector).
- `examples/legacy-tscc-docker`: arquivos Docker antigos do TSCC (histórico de migração).
- `docs/`: documentação consolidada da integração.

## Docker

O `docker-compose.yaml` da raiz concentra os 4 serviços principais + os simuladores remotos do TSRE:

- **Comunicação**: `comm` (OMNeT++)
- **Agentes**: `pade`
- **Cenário Mosaik**: `mosaik` (engine + collectors)
- **Rede elétrica (TSRE)**: imagem única instanciada como `opendss`, `battery`, `controller`,
  `csv-data-1`, `csv-data-2`, `inverter-std`, `pv-panel`, `regulator`, `smart-inverter`

Comandos úteis:

```bash
docker compose build
docker compose up comm pade mosaik
docker compose up -d opendss battery csv-data-1 csv-data-2 inverter-std pv-panel regulator smart-inverter
```

O controle de bateria, antes em `grid-opentes/src/simulators/controller_sim.py`,
migrou para um agente PADE em `pade-opentes/agents/controller_agent.py`. Ele
sobe como serviço opcional `pade-controller` via profile:

```bash
docker compose --profile controller up pade-controller
```

O agente expõe a porta Mosaik `5681` (publicada como `15681` no host). Cenários
Mosaik conectam via `'BatteryController': {'connect': 'pade-controller:5681'}`.

### Cenário IEEE 13 Bus com Smart PV (`ieee13`)

Absorvido do upstream `grei-ufc/tsre-der-opentes` (branch `paulo-victor`) e
adaptado para a topologia de 4 containers. Rede elétrica IEEE 13 + 5 PVs +
inversores, com collector elétrico remoto. Roda via profile `ieee13`:

```bash
docker compose --profile ieee13 up --abort-on-container-exit \
  --exit-code-from mosaik-ieee13 mosaik-ieee13
```

Resultado em `output/result_run_ieee13_cosim_pv_5min.csv` (288 passos, 66 colunas).
Dashboard pós-simulação: `docker compose run --rm --no-deps mosaik python plot_ieee13.py`.

> Nota: as loadshapes do IEEE 13 PV são geradas por
> `simulators_teams/grid-opentes/src/simulators/gen_pv_loadshapes.py` a partir
> dos CSVs (o upstream não as fornecia). Ver `docs/ALTERACOES_INTEGRACAO.txt` seção 13.

### Demo do controlador PADE (`controller-demo`)

Exercita o agente `BatteryControllerAgent` em loop fechado com uma bateria:

```bash
docker compose --profile controller-demo up --abort-on-container-exit \
  --exit-code-from mosaik-controller-demo mosaik-controller-demo
```

### Cenário integrado dos 4 containers (`integrated`)

Roda comunicação (OMNeT++/PADE) **e** rede elétrica (IEEE 13 PV) no mesmo mundo
Mosaik, usando os 4 simulators_teams:

```bash
docker compose --profile integrated up --abort-on-container-exit \
  --exit-code-from mosaik-integrated mosaik-integrated
```

> **Atenção operacional**: os simuladores `--remote` do grid aceitam uma única
> conexão Mosaik e encerram após. Cada execução precisa de containers de
> simulador frescos. Não sondar as portas `--remote` com TCP de readiness (isso
> consome a conexão e mata o simulador) — sondar apenas o `comm` (5555, ZMQ).

Para o cenário Docker do TSRE, suba os simuladores TSRE e rode o cenário no host:

```bash
cd simulators_teams/grid-opentes
uv run --no-sync python src/scenarios/cenariodocker.py
```

Mais contexto está em `docs/INTEGRACAO.md`.

## Ambiente local

Para instalar os componentes Python em uma `.venv` única:

```bash
uv sync
```

Probe de compatibilidade TSCC/Mosaik:

```bash
uv run python examples/tscc-mosaik-compat/check_tscc_mosaik_compat.py
```
