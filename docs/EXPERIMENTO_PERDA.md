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
| `loss025`…`loss045` | 0,25 / 0,30 / 0,35 / 0,40 / 0,45 | Faixa densa em torno do limiar. |
| `loss050` | 0,5 | Metade das medições se perde. |
| `loss075` | 0,75 | 75% das medições se perde. |
| `loss100` | 1,0 | Sem comunicação: nenhuma medição chega. |

O **ganho do Volt/Var** foi mantido no padrão (`Q_MAX_PCT = 0,05`,
`V_DEADBAND = 0,02`) em todas as rodadas, de modo que a **única** variável é a
qualidade da comunicação. Barra de referência: **652** (PV5), a mais crítica
(subtensão no fim do alimentador).

## Como reproduzir

```bash
./run_loss_sweep.sh        # baseline + perda 0..100% (restaura o omnetpp.ini ao fim)
# ou um subconjunto:  ./run_loss_sweep.sh loss030 loss040
docker compose run --rm --no-deps -e MOSAIK_OUTPUT_DIR=/app/output/sensibilidade_perda \
  mosaik python plot_loss_sweep.py
```

Saídas em `output/sensibilidade_perda/`: `result_<tag>.csv`, `comm_trace_<tag>.csv`
e `sensibilidade_perda.png`.

> O `run_loss_sweep.sh` edita o `drop_probability` no `omnetpp.ini` (montado por
> volume no `comm`) antes de cada passada e **restaura o valor original** ao final
> (mesmo se interrompido). Nada permanente é alterado no modelo.

## Resultados (Bus 652)

| Perda | Entregue | V média | **lift médio** | V mín | t < 0,95 | Q médio |
|---:|---:|---:|---:|---:|---:|---:|
| baseline | 100% | 0,9773 | 0,0 mV | 0,9205 | 26,4% | 0 |
| **0%** | 100% | 0,9827 | **+5,4 mV** | 0,9382 | 20,1% | 87 kvar |
| **25%** | 76% | 0,9827 | **+5,4 mV** | 0,9382 | 20,1% | 87 kvar |
| **30%** | 70% | 0,9760 | **−1,3 mV** | 0,9220 | 21,5% | 70 kvar |
| **35%** | 64% | 0,9760 | **−1,5 mV** | 0,9220 | 21,5% | 69 kvar |
| **40%** | 59% | 0,9730 | **−3,8 mV** | 0,9210 | 26,4% | 64 kvar |
| **45%** | 54% | 0,9760 | **−1,6 mV** | 0,9220 | 21,5% | 67 kvar |
| **50%** | 49% | 0,9734 | **−3,8 mV** | 0,9205 | 26,4% | 64 kvar |
| **75%** | 24% | 0,9740 | **−3,7 mV** | 0,9205 | 26,4% | 64 kvar |
| **100%** | 0% | 0,9773 | 0,0 mV | 0,9205 | 26,4% | 0 |

*Entregue% = `packets_sent / (packets_sent + packets_dropped)`. lift médio = Δ da
tensão média da barra 652 vs baseline (+ ajuda / − atrapalha). Q médio = Σ|Q| dos
5 inversores, média no dia (esforço de controle).*

## Leitura da figura (`sensibilidade_perda.png`)

Painel 1 = curvas no tempo; painéis 2–4 = **barras por nível de perda** (uma barra
por cenário, gradiente verde→vermelho):

1. **Tensão da barra 652 ao longo do dia.** As curvas de baixa perda (verdes) se
   descolam para cima no fim do dia (suporte de tensão); as de alta perda e o
   baseline (preto pontilhado) ficam coladas no patamar baixo. **Repare nas curvas
   de 30/35/45%**: à noite elas sobem **acima de 1,0 pu** — ver "Anomalia" abaixo.
2. **Benefício do controle (lift médio).** Barra divergente: verde (+5,4 mV) em
   0% e 25%, vermelha (negativa) de 30% a 75%, e ~0 em 100%. Mostra o limiar:
   o sinal vira entre 25% e 30%.
3. **Esforço de controle (Q injetado).** ~87 kvar até 25%, ~64–70 kvar de 30% a
   75%, e ~0 em 100%.
4. **Informação entregue.** Queda quase linear de 100% a 0%.

### Anomalia verificada: sobretensão noturna em 30/35/45% de perda

Nas curvas de 30/35/45% a tensão da barra 652 **sobe acima de 1,0 pu de
madrugada** (~1,018 pu), enquanto baseline, 0%, 25%, 40%, 50%, 100% ficam no
patamar baixo. **Foi verificado e é um resultado REAL, não um artefato** de plot
ou de borda do loadshape (a irradiância já é 0 à noite e o baseline fica
totalmente plano no último passo). A causa: com perda alta, os controladores
**PV1–PV4 perdem a comunicação e seguram um `Q` de boost** (chega a injetar
30–105 kvar à noite, quando deveriam estar ~0); esse reativo preso **sobre-injeta**
e empurra o alimentador à **sobretensão**. É a mesma "ação sobre dado velho" da
conclusão, agora se manifestando como **violação de tensão** — é intermitente
entre níveis (30/35/45% sim; 40/50% não) porque depende de *quais* pacotes caem
(semente única). Ou seja, comunicação ruim não só anula o controle: pode
**desestabilizá-lo** e gerar violação de tensão.

> **As tabelas e a figura acima são de UMA semente.** O "penhasco abrupto em
> 25–30%" que ela sugere é, em boa parte, **ruído de semente única** — ver a
> análise multi-semente abaixo, que é a conclusão robusta.

## Multi-semente — varredura completa 0–100% (passo 5%, 20 sementes)

Para responder "**até que perda o controle continua bom?**", varremos a perda de
**0% a 100% em passos de 5%**, cada nível com **20 sementes** (`seed-0-mt` =
1..20, via `run_loss_multiseed.sh`), e agregamos média ± desvio. 0% e 100% são
determinísticos (1 rodada). Figura: `sensibilidade_perda_multiseed.png`.

| Perda | lift médio ± dp [mV] | Sobretensão | Perda | lift médio ± dp [mV] | Sobretensão |
|---:|---:|:--:|---:|---:|:--:|
| **0%** | **+5,4** (det.) | 0/1 | 55% | −0,5 ± 3,9 | 4/20 |
| 5% | −0,6 ± 3,6 | 9/20 | 60% | −0,2 ± 3,3 | 8/20 |
| 10% | −0,1 ± 3,7 | 9/20 | 65% | −0,2 ± 3,9 | 5/20 |
| 15% | +1,7 ± 4,2 | 4/20 | 70% | −0,8 ± 3,1 | 6/20 |
| 20% | +0,4 ± 4,2 | 5/20 | 75% | +0,1 ± 3,6 | 4/20 |
| 25% | +0,1 ± 4,0 | 6/20 | 80% | +1,3 ± 3,7 | 4/20 |
| 30% | −1,5 ± 3,6 | 4/20 | 85% | −0,8 ± 2,8 | 6/20 |
| 35% | +0,5 ± 3,7 | 9/20 | 90% | +1,0 ± 3,5 | 4/20 |
| 40% | +0,6 ± 4,0 | 6/20 | 95% | +1,7 ± 2,3 | 7/20 |
| 45% | +0,2 ± 3,9 | 6/20 | **100%** | **0,0** (det.) | 0/1 |
| 50% | −0,8 ± 3,3 | 8/20 | | | |

*(Q médio ≈ 72–78 kvar em toda a faixa 5–95%; Entregue% = 100 − perda%.)*

### O ponto de quebra é entre 0% e 5%

A varredura fina dá a resposta — e ela é **mais dura do que se imaginava**:

- **Só com 0% de perda o controle é bom e confiável** (lift **+5,4 mV**,
  determinístico, **sem sobretensão**).
- **Já com 5% de perda o benefício confiável some.** De 5% a 95% o lift médio
  fica **preso perto de zero** (oscila entre −1,5 e +1,7 mV) com desvio entre
  sementes **±3 a 4 mV — maior que a própria média**. Ou seja, em toda essa faixa
  o ganho é **estatisticamente indistinguível de zero**: o controle ora ajuda,
  ora atrapalha, ao sabor de *quais* pacotes caem. Não existe "robusto até X%": a
  confiabilidade cai de um degrau já na primeira perda.
- **O risco de sobretensão noturna existe em qualquer perda** (≈ 4 a 9 das 20
  sementes, 20–45%, sem tendência clara ao longo de 5–95%), e **nunca** em 0% ou
  100%. É a manifestação do dado velho: Q de boost preso → sobre-injeção →
  V > 1,0 pu de madrugada.

## Conclusões

- **Comunicação perfeita (0% perda) ⇒ único regime de controle bom.** Lift
  +5,4 mV, ~87 kvar, sem sobretensão.
- **Qualquer perda (≥5%) ⇒ controle NÃO-CONFIÁVEL e ARRISCADO.** O benefício médio
  é ~0 com alta variância (ora ajuda, ora atrapalha) e há **risco de sobretensão**
  (~20–45% das rodadas) em toda a faixa. **Não existe ponto de operação "parcial"
  seguro** — basta começar a perder pacotes para não dar mais para confiar no
  controle.
- **Sem comunicação (100% perda) ⇒ controle inerte.** `Q = 0`, idêntico ao
  baseline, sem sobretensão.

É a versão forte (e agora estatisticamente apoiada por uma varredura de 0 a 100%)
da tese do projeto: **não basta o controlador agir — ele precisa de informação a
tempo e confiável**. Comunicação degradada não dá um "meio-controle": ela torna o
controle **imprevisível e potencialmente danoso** antes de simplesmente pará-lo.

## Como reproduzir o multi-semente

```bash
./run_loss_multiseed.sh     # 7 níveis estocásticos × 20 sementes + det. (resumível)
docker compose run --rm --no-deps \
  -e MOSAIK_OUTPUT_DIR=/app/output/sensibilidade_perda_multiseed \
  mosaik python plot_loss_multiseed.py
```

Relacionado: a discussão fenomenológico × mecanístico do modelo de perda está em
[`INTEGRACAO.md`](INTEGRACAO.md#a-perda-de-pacotes-é-parâmetro-não-resultado).
