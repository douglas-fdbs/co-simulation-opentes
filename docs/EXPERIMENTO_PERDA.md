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
| `loss025` | 0,25 | 25% das medições se perde. |
| `loss050` | 0,5 | Metade das medições se perde. |
| `loss075` | 0,75 | 75% das medições se perde. |
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
| `loss025` (25% perda) | 76% | 0,9827 | **+5,4 mV** | 0,9382 | 20,1% | 87 kvar |
| `loss050` (50% perda) | 49% | 0,9734 | **−3,8 mV** | 0,9205 | 26,4% | 64 kvar |
| `loss075` (75% perda) | 24% | 0,9740 | **−3,7 mV** | 0,9205 | 26,4% | 64 kvar |
| `loss100` (100% perda) | 0% | 0,9773 | 0,0 mV | 0,9205 | 26,4% | 0 |

*Entregue% = `packets_sent / (packets_sent + packets_dropped)`. lift médio = Δ da
tensão média da barra 652 vs baseline (+ ajuda / − atrapalha). Q médio = Σ|Q| dos
5 inversores, média no dia (esforço de controle).*

## Leitura da figura (`sensibilidade_perda.png`)

1. **Tensão da barra 652 ao longo do dia.** As curvas de **0% e 25% perda**
   (verdes) se descolam para cima no fim do dia (suporte de tensão) e ficam
   **sobrepostas**. As de 50%, 75%, 100% e o baseline ficam **coladas** no
   patamar baixo.
2. **Benefício do controle (lift médio).** Barra divergente, e é o "penhasco":
   **+5,4 mV** com 0% e 25% (ajuda), **−3,8 / −3,7 mV** com 50% e 75% (atrapalha),
   **0** com 100% e baseline.
3. **Esforço de controle (Q injetado).** 87 kvar (0% e 25%) → 64 kvar (50% e 75%)
   → 0 (100%).
4. **Informação entregue.** 100% → 76% → 49% → 24% → 0%, acompanhando o parâmetro.

## Conclusões

A degradação **não é suave** — há um **limiar** (entre 25% e 50% de perda) em que
o controle passa de eficaz para contraproducente, e três regimes claros:

- **Robusto até ~25% de perda ⇒ controle efetivo.** Com 0% **e 25%** de perda o
  resultado é **o mesmo** (mínima 0,920 → 0,938 pu; tempo em subtensão 26% → 20%;
  ~87 kvar). A tensão muda devagar (passos de 5 min), então perder 1 em 4
  medições ainda deixa o controlador **suficientemente informado**. Boa notícia:
  o controle tolera uma rede imperfeita até certo ponto.
- **Perda alta (50–75%) ⇒ controle contraproducente.** O achado mais importante:
  o controlador **ainda injeta reativo** (~64 kvar), mas sobre **dados
  desatualizados** — entre uma medição e outra ele segura o último `Q`, que já não
  corresponde à tensão atual. O efeito líquido vira **negativo** (lift −3,8/−3,7
  mV): **esforço de controle sem informação fresca vira esforço desperdiçado, ou
  pior, prejudicial**.
- **Sem comunicação (100%) ⇒ controle inexistente.** O controlador nunca recebe a
  tensão, segura `Q = 0` e o resultado é **idêntico ao baseline**. Valida o modelo
  (ausência de informação anula o controle, sem quebrar a simulação).

É a versão forte da tese do projeto: **não basta o controlador agir — ele precisa
de informação a tempo**; comunicação ruim pode ser pior do que não ter controle.

> **Ressalva metodológica.** Os números são de **uma realização** (semente fixa;
> *quais* pacotes se perdem é sorteado). O efeito qualitativo (robusto até ~25%,
> contraproducente em 50–75%, inerte em 100%) é coerente com o mecanismo (dado
> velho → ação no instante errado), mas a **posição exata do limiar** e o **valor**
> do lift variam com a semente. Para quantificar com barras de erro, repetir cada
> nível com várias sementes (`seed-0-mt` no `omnetpp.ini`) e tirar média/desvio —
> fica como próximo passo.

Relacionado: a discussão fenomenológico × mecanístico do modelo de perda está em
[`INTEGRACAO.md`](INTEGRACAO.md#a-perda-de-pacotes-é-parâmetro-não-resultado).
