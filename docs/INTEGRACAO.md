# Integração OpenTES

Este documento resume a organização inicial do repositório agregador
`co-simulation-opentes` e o estado atual da integração entre os simuladores dos
times TTESO, TSCC e TSRE.

## Objetivo

O fluxo alvo desta etapa é:

```text
PADE -> Mosaik -> OMNeT++ -> Mosaik -> PADE/DSO -> Mosaik -> OpenDSS
```

O benchmark operacional inicial é o IEEE 13 Bus. A ideia é validar primeiro a
comunicação entre domínios e, em seguida, substituir mensagens artificiais por
payloads com semântica elétrica e de controle.

## Estrutura

- `simulators_teams/tteso-tes-opentes`: PADE atualizado para Python 3.12 e
  exemplos de agentes/sistemas elétricos.
- `simulators_teams/tscc-com-opentes`: integração PADE + Mosaik + OMNeT++ para
  simulação de comunicação.
- `simulators_teams/tsre-der-opentes`: simuladores de rede elétrica/DERs,
  OpenDSS via `py-dss-interface` e cenários Mosaik.
- `examples/mosaik-docker-example`: exemplo original do repositório, preservado
  como referência simples de dockerização.
- `examples/tscc-mosaik-compat`: probe reutilizável para verificar a
  compatibilidade do adaptador TSCC com a versão de Mosaik instalada.
- `examples/legacy-tscc-docker`: arquivos Docker antigos do TSCC, mantidos apenas como
  memória de migração.

## Decisões Técnicas

- O repositório raiz é o agregador dos componentes usados nesta etapa.
- Os `.git` internos dos repositórios importados foram removidos para que o
  agregador versione a base integrada.
- O TSCC usa um único `Dockerfile` multi-stage com targets para Mosaik, PADE e
  OMNeT++.
- A versão comum de Mosaik é `3.5.0`, porque o TSRE já estava alinhado nela e o
  TSCC foi validado nessa mesma versão.
- O `py-dss-interface>=2.3.0` é usado diretamente no Linux. A versão atual
  fornece wheels Linux, dispensando a compilação manual da engine OpenDSS nos
  testes realizados.
- A porta interna `5678` do PADE/TSCC é publicada como `15678` no host para
  evitar conflito com o serviço `pv-panel` do TSRE.

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

Smoke integrado do TSCC:

```bash
docker compose up --abort-on-container-exit --exit-code-from mosaik_master mosaik_master
docker compose down --remove-orphans
```

Validação do cenário IEEE 13 do TSRE em container:

```bash
docker compose run --rm --no-deps opendss python -u /app/src/scenarios/opendss_scenario.py
docker compose down --remove-orphans
```

O `docker compose down` é importante porque os serviços auxiliares do TSCC podem
continuar vivos após o encerramento do `mosaik_master`.

## Testes Executados

Estado validado nesta organização:

- Imports gerais do ambiente Python integrado.
- Imports dos módulos TSCC/Mosaik, TSCC/PADE e TSRE.
- `pade version`, retornando PADE `3.0`.
- OpenDSS IEEE 13 direto via `py-dss-interface`, convergindo no Linux.
- Cenário TSRE `opendss_scenario.py`, local e em container, com 144 passos de
  10 minutos.
- Probe TSCC com PADE falso e com PADE real remoto.
- Build Docker de `pade-runtime`, `pade`, `mosaik_master`, `opendss` e
  `omnet_sim`.
- Compile-test do modelo OMNeT++ com ZMQ.
- Smoke integrado TSCC com PADE, Mosaik e OMNeT++ por 20 passos e 50
  periféricos.

Artefatos como `results.csv`, `grafico_trafego.png`, `sim_exec`, `out/` e
saídas do OpenDSS são produtos de simulação e estão no `.gitignore`.
