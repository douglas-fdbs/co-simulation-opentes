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

A pasta `examples/` (exemplos e legados de dockerização do TSCC) foi removida em
2026-06-11 por não fazer parte do runtime. Ver `ALTERACOES_INTEGRACAO.txt`.

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
