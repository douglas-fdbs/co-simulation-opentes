#!/usr/bin/env bash
#
# run.sh - entrypoint unico do OpenTES: cenarios de co-simulacao e experimentos.
#
# Substitui os antigos run_opentes.sh, run_48h.sh, run_loss_sweep.sh e
# run_loss_multiseed.sh, que duplicavam a mesma logica de orquestracao.
#
#   ./run.sh --help        lista todos os comandos
#   ./run.sh integrated    co-simulacao completa (o comando do dia a dia)
#
# Nota de infra: containers de profile nao sao removidos por um "docker compose
# down" simples e seguram a rede ("Resource is still in use"), deixando um ID
# stale que quebra o proximo up. Por isso _cleanup() faz limpeza COMPLETA
# (todos os profiles + rede + orfaos) antes e depois de cada passada, garantindo
# simuladores --remote frescos.

set -euo pipefail
cd "$(dirname "$0")"

# ============================================================================
# Configuracao comum
# ============================================================================
INI="simulators/comm-opentes/omnetpp.ini"
ALL_PROFILES=(--profile ieee13 --profile integrated --profile market)
# simuladores que precisam estar de pe antes do mosaik conectar
DEPS=(comm pade-integrated opendss pv-panel csv-data-1 csv-data-2 elec-collector)
RESULT=""   # preenchido por cada comando; exibido no final

usage() {
    cat <<'EOF'
OpenTES - co-simulacao multidominio (PADE + OMNeT++ + OpenDSS via Mosaik)

Uso: ./run.sh <comando> [opcoes]

Cenarios:
  integrated              Co-simulacao COMPLETA (PADE + OMNeT++ + OpenDSS).
                          Roda 2 passadas: baseline (sem controle) e Volt/Var.
  ieee13                  Rede eletrica isolada (OpenDSS + Smart PV).
  star                    Comunicacao isolada (PADE + OMNeT++).
  market                  Mercado transativo na rede MVLV75: negociacao
                          multiagente (PADE) + OpenDSS. Roda 2 passadas:
                          baseline (sem negociacao) e negociado.
                          EXIGE um solver: export CPLEX_HOME=... (ver
                          simulators/market-opentes/README.md).

Experimentos:
  48h                     Cenario integrado em horizonte de 48h (2 dias com a
                          mesma irradiancia) para verificar se o ciclo diario
                          se repete. Perda 0%.
  loss-sweep [tags...]    Sensibilidade do Volt/Var a perda de pacotes:
                          baseline + perda 0/25/30/35/40/45/50/75/100%,
                          1 semente. Sem argumentos roda tudo; com argumentos
                          roda so as passadas indicadas (ex.: loss030 loss035).
  loss-multiseed          Idem, varredura completa 0-100% (passo 5%) com 20
                          sementes por nivel estocastico, para media/desvio.
                          Resumivel: pula passadas ja concluidas.

Outros:
  -h, --help              Mostra esta ajuda.

Exemplos:
  ./run.sh integrated
  ./run.sh loss-sweep loss030 loss035
EOF
}

# ============================================================================
# Internals (antes duplicados nos 4 scripts)
# ============================================================================

# Limpeza completa do estado do Docker (profiles + containers + rede).
_cleanup() {
    docker compose "${ALL_PROFILES[@]}" down --remove-orphans >/dev/null 2>&1 || true
    docker ps -aq --filter "name=opentes" | xargs -r docker rm -f >/dev/null 2>&1 || true
    docker network rm opentes-integration_opentes-net >/dev/null 2>&1 || true
}

# Espera o comm (OMNeT++) compilar e abrir sua porta ZMQ (5555).
# So o comm pode ser sondado por TCP: e ZMQ e aceita multiplas conexoes.
_wait_comm() {
    echo ">> aguardando o comm (OMNeT++) compilar (porta 5555)..."
    until python3 -c "import socket; socket.create_connection(('localhost',5555),timeout=1).close()" 2>/dev/null; do
        sleep 2
    done
    sleep 3
}

# Espera os simuladores --remote ficarem prontos.
#
# ATENCAO: NAO sondar as portas --remote (5671/5673/5675/5676/5678/5680) com um
# connect TCP. Elas aceitam UMA unica conexao (a do mosaik) e encerram em
# seguida: um probe consome essa conexao e MATA o simulador. Verificado na
# pratica — o container sai logo apos o probe. Ver o aviso no README.
# Por isso a prontidao e detectada pelo LOG, que nao toca no socket.
#   $1 = profile do compose
_wait_remote_sims() {
    local profile="$1" i
    echo ">> aguardando os simuladores --remote ficarem prontos..."
    for i in $(seq 1 60); do
        if docker compose --profile "$profile" logs elec-collector 2>/dev/null \
                | grep -q "Waiting for connection"; then
            sleep 3   # margem para os demais simuladores do mesmo lote
            return 0
        fi
        sleep 1
    done
    echo "!! timeout aguardando o elec-collector ficar pronto" >&2
    return 1
}

# --- omnetpp.ini: leitura, escrita e restauracao ---------------------------
_set_drop()   { sed -i -E "s/(node_0\.drop_probability = ).*/\1${1}/" "$INI"; }
_set_seed()   { sed -i -E "s/^(seed-0-mt = ).*/\1${1}/" "$INI"; }
_set_simlim() { sed -i -E "s/^(sim-time-limit = ).*/\1${1}/" "$INI"; }

ORIG_DROP="$(grep -E 'node_0\.drop_probability' "$INI" | sed -E 's/.*=[[:space:]]*//')"
ORIG_SEED="$(grep -E '^seed-0-mt'               "$INI" | sed -E 's/.*=[[:space:]]*//')"
ORIG_SIMLIM="$(grep -E '^sim-time-limit'        "$INI" | sed -E 's/.*=[[:space:]]*//')"

# Restaura o ini mesmo se o script for interrompido no meio (Ctrl-C, erro).
_ini_restore() {
    _set_drop   "$ORIG_DROP"
    _set_seed   "$ORIG_SEED"
    _set_simlim "$ORIG_SIMLIM"
}
trap _ini_restore EXIT

# Uma passada do cenario integrado. O estado do ini (perda/semente) e as
# variaveis de ambiente (MOSAIK_OUTPUT_DIR, MOSAIK_N_PASSOS, ...) devem ser
# ajustados pelo chamador antes.
#   $1 = tag (nome do arquivo de saida) | $2 = CONTROL_ENABLED (0/1)
_run_pass() {
    local tag="$1" control="$2"
    _cleanup
    CONTROL_ENABLED="$control" RESULT_TAG="$tag" \
        docker compose --profile integrated up -d "${DEPS[@]}"
    # o comm (OMNeT++) precisa compilar; por ser o mais lento a ficar pronto,
    # esperar por ele ja da tempo dos simuladores --remote ligarem
    _wait_comm
    CONTROL_ENABLED="$control" RESULT_TAG="$tag" \
        docker compose --profile integrated up --abort-on-container-exit \
            --exit-code-from mosaik-integrated mosaik-integrated
}

# Espera o processo PADE do mercado subir os 33 agentes.
# A prontidao e detectada pela linha "[market-mas] pronto", emitida DEPOIS do
# listenTCP de todos os agentes. Esperar pela linha que anuncia a criacao dos
# agentes nao serve: ela sai antes das portas abrirem, e o mosaik conecta cedo
# demais e morre com "Could not connect to pade-market:5678".
_wait_pade_market() {
    local i
    echo ">> aguardando os agentes PADE do mercado..."
    for i in $(seq 1 60); do
        if docker compose --profile market logs pade-market 2>/dev/null \
                | grep -q "market-mas. pronto"; then
            sleep 2
            return 0
        fi
        sleep 1
    done
    echo "!! timeout aguardando o pade-market" >&2
    return 1
}

# Uma passada do cenario de mercado.
#   $1 = tag (nome do arquivo de saida) | $2 = MARKET_NEGOTIATE (0/1)
_run_market_pass() {
    local tag="$1" negotiate="$2"
    local operation="${MARKET_OPERATION:-1}"
    # A rede ve a demanda realizada nas DUAS passadas; o que muda e se os
    # agentes reagem a ela.
    _cleanup
    # As MESMAS variaveis nas duas chamadas do compose. Passar MARKET_NEGOTIATE
    # so na segunda faz o compose ver a configuracao do pade-market mudar e
    # RECRIAR o container bem na hora em que o mosaik conecta, o que aparece
    # como "Could not connect to pade-market:5678".
    RESULT_TAG="$tag" MARKET_NEGOTIATE="$negotiate" MARKET_OPERATION="$operation" \
        docker compose --profile market up -d opendss elec-collector pade-market
    _wait_pade_market
    RESULT_TAG="$tag" MARKET_NEGOTIATE="$negotiate" MARKET_OPERATION="$operation" \
        docker compose --profile market up --abort-on-container-exit \
            --exit-code-from mosaik-market mosaik-market
}

# Gera uma figura a partir dos resultados frescos.
#   $1 = dir de saida (caminho do container) | $2 = script | $3 = servico
_plot() {
    docker compose run --rm --no-deps -e MOSAIK_OUTPUT_DIR="$1" \
        "${3:-mosaik-integrated}" python "$2"
}

# ============================================================================
# Comandos
# ============================================================================

cmd_star() {
    docker compose up --abort-on-container-exit --exit-code-from mosaik comm pade mosaik
    RESULT="output/star/  (results.csv + grafico_trafego.png)"
}

cmd_ieee13() {
    # sobe os simuladores --remote ANTES do mosaik: o depends_on do compose so
    # garante que o container iniciou, nao que o app esta ouvindo — sem isso o
    # mosaik conecta cedo demais e a run morre com "Could not connect to
    # elec-collector:5673". Este cenario nao tem comm, entao a espera e por log.
    docker compose --profile ieee13 up -d \
        opendss pv-panel smart-inverter csv-data-1 csv-data-2 elec-collector
    _wait_remote_sims ieee13
    docker compose --profile ieee13 up --abort-on-container-exit \
        --exit-code-from mosaik-ieee13 mosaik-ieee13
    echo ">> gerando dashboard a partir do resultado fresco..."
    _plot /app/output/ieee13 plot_ieee13.py mosaik-ieee13
    RESULT="output/ieee13/  (result_run_ieee13_cosim_pv_5min.csv + ieee13_dashboard.png)"
}

cmd_integrated() {
    # duas passadas: sem controle (baseline) e com controle (Volt/Var)
    echo ">> [integrated] passada 'baseline' (sem controle)"
    _run_pass baseline 0
    echo ">> [integrated] passada 'volt_var' (com controle)"
    _run_pass volt_var 1
    echo ">> gerando dashboard a partir dos resultados frescos..."
    _plot /app/output/integrated plot_integrated.py
    RESULT="output/integrated/  (result_baseline.csv, result_volt_var.csv + comm_trace_*.csv + dashboard_integrated.png)"
}

cmd_market() {
    # O solver nao esta no repositorio nem na imagem (licenca). Ver
    # simulators/market-opentes/README.md.
    if [ ! -x "${CPLEX_HOME:-/nao-definido}/bin/x86-64_linux/cplex" ]; then
        echo "!! CPLEX nao encontrado." >&2
        echo "   Defina CPLEX_HOME apontando para a sua instalacao, por exemplo:" >&2
        echo "     export CPLEX_HOME=\$HOME/IBM/CPLEX_Studio2211/cplex" >&2
        echo "   Detalhes e alternativas em simulators/market-opentes/README.md" >&2
        exit 1
    fi
    export CPLEX_HOME
    # duas passadas: sem negociacao (linha de base) e com negociacao
    # A linha de base nao tem mecanismo de mercado nenhum: nem negociacao do dia
    # seguinte, nem correcao na operacao. A rede ve a mesma demanda realizada nas
    # duas passadas, entao a comparacao isola o efeito do mecanismo.
    echo ">> [market] passada 'baseline' (programacao dos prosumidores, sem mecanismo)"
    MARKET_OPERATION=0 _run_market_pass baseline 0
    echo ">> [market] passada 'negociado' (com a negociacao multiagente)"
    _run_market_pass negociado 1
    RESULT="output/market/  (result_baseline.csv, result_negociado.csv)"
}

cmd_48h() {
    export MOSAIK_N_PASSOS=576
    export MOSAIK_IRRADIANCE_FILE=ieee13_shape_pv_5min_48h.csv
    export MOSAIK_TEMPERATURE_FILE=ieee13_temperature_5min_48h.csv
    export MOSAIK_OUTPUT_DIR=/app/output/sensibilidade_48h
    mkdir -p output/sensibilidade_48h
    _set_drop 0.0          # 48h limpo: 0% de perda
    _set_simlim 200000s    # cobre as 48h
    echo ">> [48h] passada 'baseline' (576 passos)"
    _run_pass baseline 0
    echo ">> [48h] passada 'volt_var' (576 passos)"
    _run_pass volt_var 1
    RESULT="output/sensibilidade_48h/  (baseline + volt_var, 576 passos cada)"
}

cmd_loss_sweep() {
    export MOSAIK_OUTPUT_DIR=/app/output/sensibilidade_perda
    local out_host="output/sensibilidade_perda"
    mkdir -p "$out_host"

    # filtro opcional: sem argumentos roda tudo; com argumentos, so as tags dadas
    local want=("$@")
    _should_run() {
        [ ${#want[@]} -eq 0 ] && return 0
        local w; for w in "${want[@]}"; do [ "$w" = "$1" ] && return 0; done
        return 1
    }

    # tag:controle:perda  (baseline = referencia sem controle)
    local levels=(
        "baseline:0:0.0"  "loss000:1:0.0"   "loss025:1:0.25"  "loss030:1:0.30"
        "loss035:1:0.35"  "loss040:1:0.40"  "loss045:1:0.45"  "loss050:1:0.5"
        "loss075:1:0.75"  "loss100:1:1.0"
    )
    echo ">> [sweep] drop_probability original = ${ORIG_DROP} (sera restaurado ao final)"
    local entry tag control drop
    for entry in "${levels[@]}"; do
        IFS=':' read -r tag control drop <<< "$entry"
        _should_run "$tag" || continue
        echo ">> [sweep] passada '${tag}' (controle=${control}, perda=${drop})"
        _set_drop "$drop"
        _run_pass "$tag" "$control"
    done
    RESULT="${out_host}/  (figura: ./run.sh --help e veja plot_loss_sweep.py)"
}

cmd_loss_multiseed() {
    export MOSAIK_OUTPUT_DIR=/app/output/sensibilidade_perda_multiseed
    local out_host="output/sensibilidade_perda_multiseed"
    mkdir -p "$out_host"

    # resumivel: pula a passada cujo result_<tag>.csv ja existe
    _run_seeded() {
        local tag="$1" control="$2" drop="$3" seed="$4"
        if [ -f "${out_host}/result_${tag}.csv" ]; then
            echo ">> [multiseed] '${tag}' ja existe — pulando."
            return 0
        fi
        echo ">> [multiseed] passada '${tag}' (controle=${control}, perda=${drop}, seed=${seed})"
        _set_drop "$drop"
        _set_seed "$seed"
        _run_pass "$tag" "$control"
    }

    echo ">> [multiseed] originais: drop=${ORIG_DROP} seed=${ORIG_SEED} (serao restaurados)"
    # deterministicos (a semente nao muda o resultado) — 1 passada cada
    _run_seeded baseline 0 0.0 1
    _run_seeded loss000  1 0.0 1
    _run_seeded loss100  1 1.0 1
    # niveis estocasticos 5%..95% (passo 5%) x 20 sementes
    local pct s
    for pct in 05 10 15 20 25 30 35 40 45 50 55 60 65 70 75 80 85 90 95; do
        for s in $(seq 1 20); do
            _run_seeded "loss0${pct}_s${s}" 1 "0.${pct}" "$s"
        done
    done
    RESULT="${out_host}/  (figura: plot_loss_multiseed.py)"
}

# ============================================================================
# Dispatch
# ============================================================================
COMMAND="${1:-}"
[ $# -gt 0 ] && shift || true

case "$COMMAND" in
    ""|-h|--help|help) usage; exit 0 ;;
    star)              ;;
    ieee13)            ;;
    integrated)        ;;
    market)            ;;
    48h)               ;;
    loss-sweep)        ;;
    loss-multiseed)    ;;
    *)
        echo "!! comando desconhecido: '${COMMAND}'" >&2
        echo "   use ./run.sh --help" >&2
        exit 1
        ;;
esac

echo ">> [OpenTES] limpando estado anterior do Docker..."
_cleanup

echo ">> [OpenTES] executando: ${COMMAND}"
case "$COMMAND" in
    star)           cmd_star ;;
    ieee13)         cmd_ieee13 ;;
    integrated)     cmd_integrated ;;
    market)         cmd_market ;;
    48h)            cmd_48h ;;
    loss-sweep)     cmd_loss_sweep "$@" ;;
    loss-multiseed) cmd_loss_multiseed ;;
esac

echo ">> [OpenTES] limpando containers..."
_cleanup

echo ">> [OpenTES] '${COMMAND}' concluido."
echo ">> [OpenTES] resultado em: ${RESULT}"
