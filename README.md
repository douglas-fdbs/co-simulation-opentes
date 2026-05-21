# OpenTES Co-simulation Integration

Este repositório passa a ser o agregador dos componentes usados na etapa
inicial de integração do OpenTES.

## Estrutura

- `simulators_teams/tteso-tes-opentes`: componente TTESO desta etapa, representado pelo PADE atualizado para Python 3.12.
- `simulators_teams/tscc-com-opentes`: comunicação PADE + Mosaik + OMNeT++.
- `simulators_teams/tsre-der-opentes`: rede elétrica, DERs, Mosaik e OpenDSS via `py-dss-interface`.
- `examples/mosaik-docker-example`: conteúdo original do `co-simulation-opentes`, mantido como referência de dockerização simples.
- `examples/tscc-mosaik-compat`: probe de compatibilidade do adaptador TSCC com Mosaik.
- `docs/`: documentação consolidada da integração.

## Docker

O `docker-compose.yaml` da raiz concentra os serviços usados agora:

- PADE standalone: `pade-runtime`
- TSCC: `omnet_sim`, `pade`, `mosaik_master`
- TSRE: simuladores remotos `opendss`, `battery`, `collector`, `controller`,
  `csv-data-1`, `csv-data-2`, `inverter-std`, `pv-panel`, `regulator`,
  `smart-inverter`

Comandos úteis:

```bash
docker compose build
docker compose up omnet_sim pade mosaik_master
docker compose up -d opendss battery collector controller csv-data-1 csv-data-2 inverter-std pv-panel regulator smart-inverter
```

Para o cenário Docker do TSRE, suba os simuladores e rode o cenário no host:

```bash
cd simulators_teams/tsre-der-opentes
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
