# Instalação e execução

## Requisitos

- **Docker** e **Docker Compose**. Cada simulador roda no seu contêiner e nada
  além disso é instalado no host.
- **IBM CPLEX**, o solver dos modelos de otimização. A licença acadêmica é
  pessoal, então ele não está no repositório nem nas imagens: é montado do host
  em tempo de execução.

```bash
git clone https://github.com/grei-ufc/co-simulation-opentes
cd co-simulation-opentes
docker compose build        # uma vez, ou depois de mudar um Dockerfile
export CPLEX_HOME=$HOME/IBM/CPLEX_Studio2211/cplex
```

O primeiro `build` compila o OMNeT++ e leva alguns minutos.

## O console

```bash
./run.sh
```

Sem argumentos, num terminal, o `run.sh` abre o console (`cli/console.sh`). Ele
mostra o estado do ambiente (Docker, imagens, CPLEX, matrizes do caso), a
configuração atual e um menu:

| Tecla | O que faz |
|---|---|
| `1` a `5` | co-simulação, negociação centralizada, figuras, fluxo completo, regenerar o caso |
| `c` | configurar: formulação, inversor, regulador, rede entre agentes (ideal, com perda, 6TiSCH), critério e tolerância, cenários, caminho do CPLEX |
| `r` | refazer o último comando |
| `s`, `l`, `f` | resumo dos resultados, log da última execução, pasta das figuras |
| `b`, `x` | construir as imagens; derrubar contêineres presos |

Durante uma execução, a tela mostra a etapa, a rodada da negociação com o
desacordo relativo e, na operação, a hora do dia. A saída completa vai para
`output/console/`. Ctrl+C interrompe e limpa os contêineres.

A configuração fica em `.opentes.env` (fora do git) e vale para a próxima
sessão. Cada configuração grava numa pasta própria: `output/market`,
`market_por_no`, `market_equilibrado`, `market_omnet`, `market_perda` e as
combinações. Fora do console, a variável `OPENTES_SAIDA` faz o mesmo.

## Os comandos

O console só chama o `run.sh`, que também funciona direto:

| Comando | O que faz | Tempo |
|---|---|---|
| `./run.sh centralizado` | a negociação sem agentes nem Mosaik, mais a liquidação | cerca de 1 min |
| `./run.sh market` | a co-simulação completa, linha de base e negociada | cerca de 1 min; 15 a 20 com a 6TiSCH |
| `./run.sh figuras` | as figuras, a partir das saídas dos dois comandos acima | segundos |
| `./run.sh caso` | regenera o caso IEEE 13 e as matrizes de sensibilidade | cerca de 1 min |

O fluxo de um estudo completo:

```bash
./run.sh centralizado
./run.sh market
./run.sh figuras          # -> output/market/figuras/
```

O `caso` só é necessário depois de mudar o circuito, as curvas de PV ou a
alocação de armazenamento. As matrizes de sensibilidade são geradas sozinhas na
primeira execução.

## As variáveis que mudam o resultado

Todas têm valor padrão no `docker-compose.yaml`.

| Variável | Padrão | O que muda |
|---|---|---|
| `MARKET_FASE` | `1` | `1`: tensão e preço sombra por fase. `0`: por barra, com a média das fases (a formulação da tese), para comparação |
| `MARKET_DISPOSITIVO` | `independente` | inversor a quatro fios, com cada fase despachada separadamente; `equilibrado`: três fios, potência igual nas fases |
| `MARKET_REGULADOR` | `previsao` | derivações do regulador fixadas pelo ponto da previsão; `neutro` as deixa em 0 |
| `NET_BACKEND` | `ideal` | rede entre os agentes: `ideal`, `lossy` ou `omnet` (6TiSCH) |
| `NET_TIME_SCALE` | `1.0` | quanto do atraso nominal da rede vira espera de relógio; com `omnet`, use `0.02`, senão cada rodada leva minutos reais |
| `NET_DROP_PROBABILITY` | `0.0` | com `NET_BACKEND=lossy`, a probabilidade de cada mensagem se perder |
| `MARKET_SCENARIOS` | `1` | cenários por prosumidor; `1` é determinístico, `3` gera nove cenários de preço e potência |
| `MARKET_V_BACKOFF` | `1e-3` | margem nos limites de tensão, contra o erro da linearização |
| `MARKET_CRITERIO` | `relativo` | critério de parada: `relativo` à potência de cada dispositivo, ou `absoluto` (variação de λ até `MARKET_EPS`, o da tese) |
| `MARKET_EPS_REL` | `1e-3` | desacordo máximo entre concentrador e DSO, em fração da potência do dispositivo |
| `MARKET_MAX_ROUNDS` | `150` | teto de rodadas da negociação |
| `MARKET_STORAGE_PF` | `none` | fator de potência do armazenamento; `none` é a hipótese ΔQ = 0 |

```bash
MARKET_FASE=0 ./run.sh market                       # comparação: por barra
MARKET_DISPOSITIVO=equilibrado ./run.sh market      # inversor de três fios
NET_BACKEND=omnet NET_TIME_SCALE=0.02 ./run.sh market   # com a rede 6TiSCH no laço
```

## O que fica gravado

Em `output/market/`, ou em `output/market_por_no/` com `MARKET_FASE=0`:

| Arquivo | Comando | Conteúdo |
|---|---|---|
| `result_baseline.csv`, `result_negociado.csv` | `market` | tensão de cada fase de cada barra e potência de cada barra e porta, a cada 15 min |
| `run.json` | `market` | histórico da negociação distribuída e registro de cada janela da operação |
| `msg_trace.csv` | `market` com `omnet` | cada mensagem: remetente, destino, tamanho, atraso, perda |
| `figuras.npz`, `history.json` | `centralizado` | tensões, programações, λ e a trilha de cada rodada |
| `dlmp.csv`, `flexibility.csv` | `centralizado` | preço por porta e intervalo, e quanto cada prosumidor cedeu |
| `transactions.csv`, `market_series.csv` | `centralizado` | energia nos mercados bilateral e spot |
| `figuras/` | `figuras` | as figuras: tensão, demanda líquida, preço sombra, negociação, mercados e comunicação |

Por fase, o `dlmp.csv` e o `flexibility.csv` têm uma coluna `fase`, e as chaves do
armazenamento são as portas, `"671.A"`. As colunas de preço saem com o sufixo
`_signal` enquanto `MARKET_CK_EUR` não for calibrado (ver
[O modelo de mercado](mercado.md)).

## Esta documentação

O site é construído com [MkDocs](https://www.mkdocs.org/) e o tema
[Material](https://squidfunk.github.io/mkdocs-material/):

```bash
uvx --with mkdocs-material mkdocs serve -f docs/mkdocs.yml   # http://127.0.0.1:8000
uvx --with mkdocs-material mkdocs build -f docs/mkdocs.yml   # site em docs/site/
```

## Ambiente Python local

O `uv sync` cria um `.venv` com o PADE e o grid como dependências editáveis, útil
para o autocomplete da IDE e para rodar scripts fora dos contêineres. A
co-simulação em si roda nos contêineres: o OMNeT++ é C++ e o OpenDSS da imagem é
o caminho testado.
