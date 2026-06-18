#!/usr/bin/env bash
#
# run_loss_sweep.sh - sensibilidade do controle Volt/Var a perda de pacotes.
#
# Objetivo (pedido do time): medir o quanto o controle distribuido depende da
# comunicacao. Roda o cenario integrado com Volt/Var variando o drop_probability
# da rede OMNeT++ em 0%, 50% e 100%, mais uma referencia baseline (sem controle).
#
#   - perda 0%   -> canal perfeito: o Volt/Var atua plenamente.
#   - perda 50%  -> metade das medicoes se perde: o controle atua parcialmente.
#   - perda 100% -> sem comunicacao: o controlador nunca recebe a tensao, segura
#                   Q=0 -> Volt/Var inexistente (deve coincidir com o baseline).
#
# Mecanismo: edita o drop_probability no omnetpp.ini (montado por volume no comm)
# antes de cada passada e RESTAURA o valor original ao final (trap EXIT). Mantem
# o ganho do Volt/Var no padrao (Q_MAX_PCT=0.05) para isolar o efeito da PERDA.
#
# Uso:  ./run_loss_sweep.sh                  # roda todas as passadas
#       ./run_loss_sweep.sh loss025 loss075  # roda so as passadas indicadas
# Saidas: output/sensibilidade_perda/result_{baseline,loss000,loss025,loss050,
#         loss075,loss100}.csv (+ comm_trace_*.csv). Figura: plot_loss_sweep.py.

set -euo pipefail
cd "$(dirname "$0")"

# filtro opcional: se passar nomes de passada, roda so essas (reaproveita o resto)
WANT=("$@")
should_run() {
    [ ${#WANT[@]} -eq 0 ] && return 0
    local w; for w in "${WANT[@]}"; do [ "$w" = "$1" ] && return 0; done
    return 1
}

INI="simulators_teams/comm-opentes/omnetpp.ini"
OUTDIR_HOST="output/sensibilidade_perda"
OUTDIR_CONT="/app/output/sensibilidade_perda"
ALL_PROFILES=(--profile ieee13 --profile integrated)

# guarda o drop original e restaura ao sair (mesmo se interromper no meio)
ORIG_DROP="$(grep -E 'node_0\.drop_probability' "$INI" | sed -E 's/.*=[[:space:]]*//')"
restore_ini() { sed -i -E "s/(node_0\.drop_probability = ).*/\1${ORIG_DROP}/" "$INI"; }
trap restore_ini EXIT

cleanup() {
    docker compose "${ALL_PROFILES[@]}" down --remove-orphans >/dev/null 2>&1 || true
    docker ps -aq --filter "name=opentes" | xargs -r docker rm -f >/dev/null 2>&1 || true
    docker network rm opentes-integration_opentes-net >/dev/null 2>&1 || true
}

set_drop() { sed -i -E "s/(node_0\.drop_probability = ).*/\1${1}/" "$INI"; }

run_pass() {
    # $1 = tag | $2 = CONTROL_ENABLED (0/1) | $3 = drop_probability
    local tag="$1" control="$2" drop="$3"
    echo ">> [sweep] passada '${tag}'  (controle=${control}, perda=${drop})"
    set_drop "${drop}"
    cleanup
    CONTROL_ENABLED="${control}" RESULT_TAG="${tag}" MOSAIK_OUTPUT_DIR="${OUTDIR_CONT}" \
        docker compose --profile integrated up -d \
            comm pade-integrated opendss pv-panel csv-data-1 csv-data-2 elec-collector
    echo ">> [sweep] aguardando o comm (OMNeT++) compilar..."
    until python3 -c "import socket; socket.create_connection(('localhost',5555),timeout=1).close()" 2>/dev/null; do
        sleep 2
    done
    sleep 3
    CONTROL_ENABLED="${control}" RESULT_TAG="${tag}" MOSAIK_OUTPUT_DIR="${OUTDIR_CONT}" \
        docker compose --profile integrated up --abort-on-container-exit \
            --exit-code-from mosaik-integrated mosaik-integrated
}

mkdir -p "${OUTDIR_HOST}"
echo ">> [sweep] drop_probability original = ${ORIG_DROP} (sera restaurado ao final)"
cleanup

should_run baseline && run_pass baseline 0 0.0     # referencia: SEM controle
should_run loss000  && run_pass loss000  1 0.0     # Volt/Var, canal perfeito
should_run loss025  && run_pass loss025  1 0.25    # Volt/Var, 25% de perda
should_run loss050  && run_pass loss050  1 0.5     # Volt/Var, 50% de perda
should_run loss075  && run_pass loss075  1 0.75    # Volt/Var, 75% de perda
should_run loss100  && run_pass loss100  1 1.0     # Volt/Var, 100% de perda

cleanup
echo ">> [sweep] concluido. saidas em ${OUTDIR_HOST}/"
echo ">> [sweep] gere a figura:"
echo "   docker compose run --rm --no-deps -e MOSAIK_OUTPUT_DIR=${OUTDIR_CONT} mosaik python plot_loss_sweep.py"
