#!/usr/bin/env bash
#
# run_loss_multiseed.sh - versao MULTI-SEMENTE do sweep de perda de pacotes.
#
# Repete cada nivel ESTOCASTICO de perda com varias sementes para tirar
# media/desvio (barras de erro) e transformar a sobretensao intermitente numa
# FREQUENCIA. Niveis 0% e 100% sao deterministicos (sem pacote sorteado), entao
# rodam 1 vez. Mantem o ganho padrao do Volt/Var (Q_MAX_PCT=0.05).
#
# Mecanismo: edita drop_probability E seed-0-mt no omnetpp.ini antes de cada
# passada e RESTAURA ambos ao final (trap). Resumivel: pula a passada cujo
# result_<tag>.csv ja existe.
#
# Uso:  ./run_loss_multiseed.sh
# Saidas: output/sensibilidade_perda_multiseed/result_<tag>.csv (tag = lossNNN_sS),
#         + comm_trace_<tag>.csv. Figura: plot_loss_multiseed.py.

set -euo pipefail
cd "$(dirname "$0")"

INI="simulators_teams/comm-opentes/omnetpp.ini"
OUTDIR_HOST="output/sensibilidade_perda_multiseed"
OUTDIR_CONT="/app/output/sensibilidade_perda_multiseed"
ALL_PROFILES=(--profile ieee13 --profile integrated)

SEEDS=($(seq 1 20))
# niveis estocasticos: varredura completa 5%..95% em passos de 5% ("tag:drop").
# (0% e 100% sao deterministicos -> rodam 1 vez, mais abaixo.)
STOCH=()
for pct in 05 10 15 20 25 30 35 40 45 50 55 60 65 70 75 80 85 90 95; do
    STOCH+=("loss0${pct}:0.${pct}")
done

# guarda valores originais e restaura ao sair (mesmo se interromper)
ORIG_DROP="$(grep -E 'node_0\.drop_probability' "$INI" | sed -E 's/.*=[[:space:]]*//')"
ORIG_SEED="$(grep -E '^seed-0-mt' "$INI" | sed -E 's/.*=[[:space:]]*//')"
restore_ini() {
    sed -i -E "s/(node_0\.drop_probability = ).*/\1${ORIG_DROP}/" "$INI"
    sed -i -E "s/^(seed-0-mt = ).*/\1${ORIG_SEED}/" "$INI"
}
trap restore_ini EXIT

cleanup() {
    docker compose "${ALL_PROFILES[@]}" down --remove-orphans >/dev/null 2>&1 || true
    docker ps -aq --filter "name=opentes" | xargs -r docker rm -f >/dev/null 2>&1 || true
    docker network rm opentes-integration_opentes-net >/dev/null 2>&1 || true
}

run_pass() {
    # $1 = tag | $2 = CONTROL_ENABLED | $3 = drop | $4 = seed
    local tag="$1" control="$2" drop="$3" seed="$4"
    if [ -f "${OUTDIR_HOST}/result_${tag}.csv" ]; then
        echo ">> [multiseed] '${tag}' ja existe — pulando."
        return 0
    fi
    echo ">> [multiseed] passada '${tag}'  (controle=${control}, perda=${drop}, seed=${seed})"
    sed -i -E "s/(node_0\.drop_probability = ).*/\1${drop}/" "$INI"
    sed -i -E "s/^(seed-0-mt = ).*/\1${seed}/" "$INI"
    cleanup
    CONTROL_ENABLED="${control}" RESULT_TAG="${tag}" MOSAIK_OUTPUT_DIR="${OUTDIR_CONT}" \
        docker compose --profile integrated up -d \
            comm pade-integrated opendss pv-panel csv-data-1 csv-data-2 elec-collector
    echo ">> [multiseed] aguardando o comm (OMNeT++) compilar..."
    until python3 -c "import socket; socket.create_connection(('localhost',5555),timeout=1).close()" 2>/dev/null; do
        sleep 2
    done
    sleep 3
    CONTROL_ENABLED="${control}" RESULT_TAG="${tag}" MOSAIK_OUTPUT_DIR="${OUTDIR_CONT}" \
        docker compose --profile integrated up --abort-on-container-exit \
            --exit-code-from mosaik-integrated mosaik-integrated
}

mkdir -p "${OUTDIR_HOST}"
echo ">> [multiseed] originais: drop=${ORIG_DROP} seed=${ORIG_SEED} (serao restaurados)"
cleanup

# referencia (sem controle) e deterministicos (semente nao importa) — 1 run cada
run_pass baseline 0 0.0 1
run_pass loss000  1 0.0 1
run_pass loss100  1 1.0 1
# niveis estocasticos x sementes
for entry in "${STOCH[@]}"; do
    lvl="${entry%%:*}"; drop="${entry##*:}"
    for s in "${SEEDS[@]}"; do
        run_pass "${lvl}_s${s}" 1 "${drop}" "${s}"
    done
done

cleanup
echo ">> [multiseed] concluido. saidas em ${OUTDIR_HOST}/"
echo ">> [multiseed] figura: docker compose run --rm --no-deps \\"
echo "     -e MOSAIK_OUTPUT_DIR=${OUTDIR_CONT} mosaik python plot_loss_multiseed.py"
