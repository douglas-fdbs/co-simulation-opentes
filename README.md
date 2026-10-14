# OpenTES: mercado transativo por fase sobre a IEEE 13 barras

Co-simulação de um mercado transativo num alimentador de distribuição
desequilibrado. Prosumidores com baterias negociam a programação do dia seguinte
com o operador da rede, e um **preço sombra por fase** coordena os dois lados para
que a tensão de cada fase fique entre 0,97 e 1,03 pu.

| Domínio | Ferramenta | Pasta |
|---|---|---|
| agentes (prosumidores, concentrador, DSO, mercado) | PADE | `simulators/pade-opentes` |
| modelos de otimização e decomposição dual | Pyomo + CPLEX | `simulators/market-opentes` |
| rede elétrica (IEEE 13 barras) | OpenDSS | `simulators/grid-opentes` |
| rede de comunicação (6TiSCH) | OMNeT++ | `simulators/comm-opentes` |
| orquestração do tempo | Mosaik | `simulators/mosaik-opentes` |

O mecanismo vem da tese de Lucas Silveira Melo (UFC, 2022), formulada para uma
rede equilibrada. Aqui ele é estendido para a IEEE 13, desequilibrada: o operador
vigia a tensão de cada fase, e o preço sombra é calculado por fase.

## Rodar

Requisitos: Docker, Docker Compose e o IBM CPLEX (licença acadêmica, montado do
host).

```bash
docker compose build
export CPLEX_HOME=$HOME/IBM/CPLEX_Studio2211/cplex
./run.sh centralizado     # a negociação sem agentes, mais a liquidação
./run.sh market           # a co-simulação completa
./run.sh figuras          # figuras em output/market/figuras/
```

`./run.sh --help` lista os comandos e as variáveis. As principais:
`MARKET_FASE=0` volta à formulação por barra, para comparação;
`MARKET_DISPOSITIVO=equilibrado` troca o inversor de quatro fios pelo de três;
`NET_BACKEND=omnet NET_TIME_SCALE=0.02` põe a rede 6TiSCH entre os agentes.

## Estrutura

```
run.sh                 ponto de entrada: market, centralizado, figuras, caso
docker-compose.yaml    os cinco contêineres: comm, grid, collector, pade, mosaik
simulators/            um diretório por domínio (tabela acima)
docs/                  a documentação: conteúdo em docs/paginas/, site em docs/site/
output/                resultados das execuções (fora do git)
```

## Documentação

O site reúne a arquitetura, o caso IEEE 13, a formulação do mercado e os
resultados:

```bash
uvx --with mkdocs-material mkdocs serve -f docs/mkdocs.yml    # http://127.0.0.1:8000
```

As páginas também podem ser lidas direto em [`docs/paginas/`](docs/paginas/).

## Autoria

Time TTESO do projeto OpenTES, [GREI](https://github.com/grei-ufc), Universidade
Federal do Ceará, sobre componentes das equipes TSCC (comunicação) e TSRE (rede
elétrica). Licença em [`LICENSE`](LICENSE).
