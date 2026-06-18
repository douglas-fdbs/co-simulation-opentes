# Experimento — Sensibilidade do Volt/Var à perda de pacotes

**Pergunta do time:** o quão impactante é, para a rede, quando a informação **não
é passada**? A hipótese é que com a comunicação em dia o controle Volt/Var atua
plena e efetivamente, e quanto menos informação chega, menos ele atua — até que,
sem comunicação, o controle seja **inexistente**.

Para responder, rodamos a co-simulação integrada (IEEE 13, 5 PVs, Volt/Var
distribuído) variando a **perda de pacotes** da rede OMNeT++ (`drop_probability`):

| Cenário | `drop_probability` | O que representa |
|---|---|---|
| `baseline` | — (controle desligado) | Referência: nenhum controle (piso de tensão). |
| `loss000` | 0,0 | Canal perfeito: toda medição chega. |
| `loss050` | 0,5 | Metade das medições se perde. |
| `loss100` | 1,0 | Sem comunicação: nenhuma medição chega. |

O **ganho do Volt/Var** foi mantido no padrão (`Q_MAX_PCT = 0,05`,
`V_DEADBAND = 0,02`) em todas as rodadas, de modo que a **única** variável é a
qualidade da comunicação. Barra de referência: **652** (PV5), a mais crítica
(subtensão no fim do alimentador).

## Como reproduzir

```bash
./run_loss_sweep.sh        # baseline + perda 0/50/100 (restaura o omnetpp.ini ao fim)
docker compose run --rm --no-deps -e MOSAIK_OUTPUT_DIR=/app/output/sensibilidade_perda \
  mosaik python plot_loss_sweep.py
```

Saídas em `output/sensibilidade_perda/`: `result_{baseline,loss000,loss050,loss100}.csv`,
`comm_trace_*.csv` e `sensibilidade_perda.png`.

> O `run_loss_sweep.sh` edita o `drop_probability` no `omnetpp.ini` (montado por
> volume no `comm`) antes de cada passada e **restaura o valor original** ao final
> (mesmo se interrompido). Nada permanente é alterado no modelo.

## Resultados (Bus 652)

| Cenário | Entregue | V média | **lift médio** | V mín | t < 0,95 | Q médio |
|---|---:|---:|---:|---:|---:|---:|
| `baseline` (sem controle) | 100% | 0,9773 | 0,0 mV | 0,9205 | 26,4% | 0 |
| `loss000` (0% perda) | 100% | 0,9827 | **+5,4 mV** | 0,9382 | 20,1% | 87 kvar |
| `loss050` (50% perda) | 49% | 0,9734 | **−3,8 mV** | 0,9205 | 26,4% | 64 kvar |
| `loss100` (100% perda) | 0% | 0,9773 | 0,0 mV | 0,9205 | 26,4% | 0 |

*Entregue% = `packets_sent / (packets_sent + packets_dropped)`. lift médio = Δ da
tensão média da barra 652 vs baseline (+ ajuda / − atrapalha). Q médio = Σ|Q| dos
5 inversores, média no dia (esforço de controle).*

## Leitura da figura (`sensibilidade_perda.png`)

1. **Tensão da barra 652 ao longo do dia.** A curva de **0% perda** (verde) é a
   única que se descola para cima no fim do dia (suporte de tensão). As de 50%,
   100% e baseline ficam praticamente **coladas** no patamar baixo.
2. **Benefício do controle (lift médio).** Barra divergente: **+5,4 mV** com 0%
   perda (ajuda), **−3,8 mV** com 50% (atrapalha), **0** com 100% e baseline.
3. **Esforço de controle (Q injetado).** 87 kvar (0%) → 64 kvar (50%) → 0 (100%).
4. **Informação entregue.** 100% → 100% → 49% → 0%, acompanhando o parâmetro.

## Conclusões

- **Comunicação em dia ⇒ controle efetivo.** Com 0% de perda, o Volt/Var eleva a
  tensão da barra crítica (mínima 0,920 → 0,938 pu; tempo em subtensão 26% → 20%)
  injetando ~87 kvar. É o melhor caso, como esperado.
- **Sem comunicação ⇒ controle inexistente.** Com 100% de perda o controlador
  nunca recebe a tensão, segura `Q = 0` e o resultado é **idêntico ao baseline**.
  Confirma a hipótese do time e valida o modelo (a ausência de informação anula o
  controle, sem quebrar a simulação).
- **Comunicação parcial não dá benefício parcial — pode atrapalhar.** O achado
  mais importante: com 50% de perda o controlador **ainda injeta reativo**
  (~64 kvar), mas sobre **dados desatualizados** — entre uma medição e outra ele
  segura o último `Q`, que pode já não corresponder à tensão atual. O efeito
  líquido sobre a tensão foi **neutro a levemente negativo** (lift médio −3,8 mV).
  Ou seja: **esforço de controle sem informação fresca vira esforço desperdiçado
  (ou contraproducente)**. É a versão forte da tese do projeto: não basta o
  controlador agir — ele precisa de informação **a tempo**.

> **Ressalva metodológica.** Os números acima são de **uma realização** (semente
> fixa; *quais* 50% se perdem é sorteado). O efeito qualitativo (esforço sem
> benefício sob perda parcial) é robusto pelo mecanismo (dado velho → ação no
> instante errado), mas o **valor** do lift no caso 50% varia conforme a semente.
> Para quantificar com barras de erro, repetir o `loss050` com várias sementes
> (`seed-0-mt` no `omnetpp.ini`) e tirar média/desvio — fica como próximo passo.

Relacionado: a discussão fenomenológico × mecanístico do modelo de perda está em
[`INTEGRACAO.md`](INTEGRACAO.md#a-perda-de-pacotes-é-parâmetro-não-resultado).
