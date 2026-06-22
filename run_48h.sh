#!/usr/bin/env bash
#
# run_48h.sh - roda o cenário integrado em horizonte de 48 HORAS (2 dias com
# irradiância igual dia-a-dia), para verificar se o ciclo diário se repete.
# Usa o solve corrigido (set_pvsystem_pq). Perda 0% (limpo). Saídas em
# output/sensibilidade_48h/ (baseline + volt_var, 576 passos cada).

set -euo pipefail
cd "$(dirname "$0")"

INI="simulators_teams/comm-opentes/omnetpp.ini"
OUTDIR_CONT="/app/output/sensibilidade_48h"
ALL_PROFILES=(--profile ieee13 --profile integrated)

export MOSAIK_N_PASSOS=576
export MOSAIK_IRRADIANCE_FILE=ieee13_shape_pv_5min_48h.csv
export MOSAIK_TEMPERATURE_FILE=ieee13_temperature_5min_48h.csv

ORIG_DROP="$(grep -E 'node_0\.drop_probability' "$INI" | sed -E 's/.*=[[:space:]]*//')"
ORIG_SIMLIM="$(grep -E '^sim-time-limit' "$INI" | sed -E 's/.*=[[:space:]]*//')"
restore_ini() {
    sed -i -E "s/(node_0\.drop_probability = ).*/\1${ORIG_DROP}/" "$INI"
    sed -i -E "s/^(sim-time-limit = ).*/\1${ORIG_SIMLIM}/" "$INI"
}
trap restore_ini EXIT
sed -i -E "s/(node_0\.drop_probability = ).*/\10.0/" "$INI"      # 48h limpo: 0% perda
sed -i -E "s/^(sim-time-limit = ).*/\1200000s/" "$INI"           # cobre as 48h

cleanup() {
    docker compose "${ALL_PROFILES[@]}" down --remove-orphans >/dev/null 2>&1 || true
    docker ps -aq --filter "name=opentes" | xargs -r docker rm -f >/dev/null 2>&1 || true
    docker network rm opentes-integration_opentes-net >/dev/null 2>&1 || true
}

run_pass() {
    local tag="$1" control="$2"
    echo ">> [48h] passada '${tag}' (controle=${control}, 576 passos)"
    cleanup
    CONTROL_ENABLED="${control}" RESULT_TAG="${tag}" MOSAIK_OUTPUT_DIR="${OUTDIR_CONT}" \
        docker compose --profile integrated up -d \
            comm pade-integrated opendss pv-panel csv-data-1 csv-data-2 elec-collector
    echo ">> [48h] aguardando o comm (OMNeT++) compilar..."
    until python3 -c "import socket; socket.create_connection(('localhost',5555),timeout=1).close()" 2>/dev/null; do
        sleep 2
    done
    sleep 3
    CONTROL_ENABLED="${control}" RESULT_TAG="${tag}" MOSAIK_OUTPUT_DIR="${OUTDIR_CONT}" \
        docker compose --profile integrated up --abort-on-container-exit \
            --exit-code-from mosaik-integrated mosaik-integrated
}

mkdir -p output/sensibilidade_48h
cleanup
run_pass baseline 0
run_pass volt_var 1
cleanup
echo ">> [48h] concluido. saidas em output/sensibilidade_48h/"
