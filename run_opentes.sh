#!/usr/bin/env bash
#
# run_opentes.sh - executa um cenario de co-simulacao OpenTES de forma robusta.
#
# Resolve o problema de rede do Docker Compose: containers de profile nao sao
# removidos por um "docker compose down" simples e seguram a rede ("Resource is
# still in use"), deixando um ID de rede stale que causa "network not found" no
# proximo up. Este script faz limpeza COMPLETA (todos os profiles + rede +
# orfaos) antes e depois de cada execucao, e garante simuladores --remote
# frescos a cada passada.
#
# Uso:
#   ./run_opentes.sh <cenario>
#
# Cenarios:
#   star             Comunicacao pura: PADE + OMNeT++ (teste isolado)
#   ieee13           Rede eletrica IEEE 13 Bus + Smart PV (teste isolado)
#   integrated       CO-SIMULACAO COMPLETA (PADE+OMNeT+++OpenDSS) — Volt/Var.
#                    Roda DUAS vezes: baseline (sem controle) e Volt/Var (com
#                    controle), para comparar a eficiencia da co-simulacao.
#
# Ex.: ./run_opentes.sh integrated

set -euo pipefail

cd "$(dirname "$0")"

SCENARIO="${1:-star}"
ALL_PROFILES=(--profile ieee13 --profile integrated)

cleanup() {
    docker compose "${ALL_PROFILES[@]}" down --remove-orphans >/dev/null 2>&1 || true
    docker ps -aq --filter "name=opentes" | xargs -r docker rm -f >/dev/null 2>&1 || true
    docker network rm opentes-integration_opentes-net >/dev/null 2>&1 || true
}

mkdir -p output/star output/ieee13 output/integrated

run_integrated_pass() {
    # $1 = tag (nome do arquivo)  |  $2 = CONTROL_ENABLED (0/1)
    local tag="$1" control="$2"
    echo ">> [OpenTES] integrated: modo '${tag}' (CONTROL_ENABLED=${control}) — deps frescos"
    cleanup
    # sobe os deps; espera o comm (OMNeT++) compilar — probe ZMQ resiliente em
    # 5555 (nesse tempo os simuladores --remote ligam e ficam prontos), evitando
    # o race em que o mosaik conecta antes do elec-collector ligar.
    CONTROL_ENABLED="${control}" RESULT_TAG="${tag}" \
        docker compose --profile integrated up -d \
            comm pade-integrated opendss pv-panel csv-data-1 csv-data-2 elec-collector
    echo ">> [OpenTES] aguardando o comm (OMNeT++) compilar..."
    until python3 -c "import socket; socket.create_connection(('localhost',5555),timeout=1).close()" 2>/dev/null; do
        sleep 2
    done
    sleep 3
    CONTROL_ENABLED="${control}" RESULT_TAG="${tag}" \
        docker compose --profile integrated up --abort-on-container-exit \
            --exit-code-from mosaik-integrated mosaik-integrated
}

echo ">> [OpenTES] limpando estado anterior do Docker..."
cleanup

echo ">> [OpenTES] executando cenario: ${SCENARIO}"
case "${SCENARIO}" in
  star)
    docker compose up --abort-on-container-exit --exit-code-from mosaik comm pade mosaik
    RESULT="output/star/  (results.csv + grafico_trafego.png)"
    ;;
  ieee13)
    docker compose --profile ieee13 up --abort-on-container-exit \
      --exit-code-from mosaik-ieee13 mosaik-ieee13
    echo ">> [OpenTES] gerando dashboard a partir do resultado fresco..."
    docker compose run --rm --no-deps -e MOSAIK_OUTPUT_DIR=/app/output/ieee13 \
      mosaik-ieee13 python plot_ieee13.py
    RESULT="output/ieee13/  (result_run_ieee13_cosim_pv_5min.csv + ieee13_dashboard.png)"
    ;;
  integrated)
    # duas passadas: sem controle (baseline) e com controle (Volt/Var)
    run_integrated_pass baseline 0
    run_integrated_pass volt_var 1
    echo ">> [OpenTES] gerando dashboard a partir dos resultados frescos..."
    docker compose run --rm --no-deps -e MOSAIK_OUTPUT_DIR=/app/output/integrated \
      mosaik-integrated python plot_integrated.py
    RESULT="output/integrated/  (result_baseline.csv, result_volt_var.csv + comm_trace_*.csv + dashboard_integrated.png)"
    ;;
  *)
    echo "!! cenario desconhecido: '${SCENARIO}'"
    echo "   use: star | ieee13 | integrated"
    exit 1
    ;;
esac

echo ">> [OpenTES] limpando containers..."
cleanup

echo ">> [OpenTES] cenario '${SCENARIO}' concluido."
echo ">> [OpenTES] resultado em: ${RESULT}"
