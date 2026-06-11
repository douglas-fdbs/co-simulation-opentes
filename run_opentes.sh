#!/usr/bin/env bash
#
# run_opentes.sh - executa um cenario de co-simulacao OpenTES de forma robusta.
#
# Resolve o problema de rede do Docker Compose: containers de profile
# (pade-controller, pade-integrated, etc) nao sao removidos por um
# "docker compose down" simples e seguram a rede ("Resource is still in use"),
# deixando um ID de rede stale que causa "network not found" no proximo up.
# Este script faz limpeza COMPLETA (todos os profiles + rede + orfaos) antes e
# depois de cada execucao, e tambem garante simuladores --remote frescos.
#
# Uso:
#   ./run_opentes.sh <cenario>
#
# Cenarios:
#   star             Comunicacao pura: PADE + OMNeT++ (default)
#   ieee13           Rede eletrica IEEE 13 Bus + Smart PV
#   controller-demo  Agente PADE controlando uma bateria
#   integrated       Os 4 containers juntos (comunicacao + rede eletrica)
#
# Ex.: ./run_opentes.sh ieee13

set -euo pipefail

cd "$(dirname "$0")"

SCENARIO="${1:-star}"
ALL_PROFILES=(--profile ieee13 --profile controller-demo --profile integrated)

cleanup() {
    docker compose "${ALL_PROFILES[@]}" down --remove-orphans >/dev/null 2>&1 || true
    # remove qualquer container/orfao remanescente do projeto
    docker ps -aq --filter "name=opentes" | xargs -r docker rm -f >/dev/null 2>&1 || true
    # remove a rede do projeto se ainda existir (evita ID stale)
    docker network rm opentes-integration_opentes-net >/dev/null 2>&1 || true
}

echo ">> [OpenTES] limpando estado anterior do Docker..."
cleanup
# garante as subpastas de output por cenario
mkdir -p output/star output/ieee13 output/controller_demo output/integrated

echo ">> [OpenTES] executando cenario: ${SCENARIO}"
case "${SCENARIO}" in
  star)
    docker compose up --abort-on-container-exit --exit-code-from mosaik comm pade mosaik
    RESULT="output/star/  (results.csv + grafico_trafego.png)"
    ;;
  ieee13)
    docker compose --profile ieee13 up --abort-on-container-exit \
      --exit-code-from mosaik-ieee13 mosaik-ieee13
    RESULT="output/ieee13/  (result_run_ieee13_cosim_pv_5min.csv)"
    ;;
  controller-demo)
    docker compose --profile controller-demo up --abort-on-container-exit \
      --exit-code-from mosaik-controller-demo mosaik-controller-demo
    RESULT="output/controller_demo/  (result_battery_controller_demo.csv)"
    ;;
  integrated)
    docker compose --profile integrated up --abort-on-container-exit \
      --exit-code-from mosaik-integrated mosaik-integrated
    RESULT="output/integrated/  (result_ieee13_integrated.csv + telemetria comm)"
    ;;
  *)
    echo "!! cenario desconhecido: '${SCENARIO}'"
    echo "   use: star | ieee13 | controller-demo | integrated"
    exit 1
    ;;
esac

echo ">> [OpenTES] limpando containers..."
cleanup

echo ">> [OpenTES] cenario '${SCENARIO}' concluido."
echo ">> [OpenTES] resultado em: ${RESULT}"
