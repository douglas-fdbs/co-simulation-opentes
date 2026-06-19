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

## Multi-semente (20 sementes por nível) — resultado robusto

Para separar sinal de ruído, repetimos cada nível estocástico com **20 sementes**
(`seed-0-mt` = 1..20, via `run_loss_multiseed.sh`) e agregamos média ± desvio.
Figura: `sensibilidade_perda_multiseed.png`.

| Perda | n | lift médio ± dp [mV] | Q ± dp [kvar] | Entregue | Sobretensão noturna |
|---:|:--:|---:|---:|---:|:--:|
| 0% | 1 | **+5,4** | 87 | 100% | 0/1 |
| 25% | 20 | +0,1 ± 4,0 | 74 ± 9 | 75% | 6/20 (30%) |
| 30% | 20 | −1,5 ± 3,6 | 72 ± 8 | 70% | 4/20 (20%) |
| 35% | 20 | +0,5 ± 3,7 | 75 ± 9 | 65% | 9/20 (45%) |
| 40% | 20 | +0,6 ± 4,0 | 75 ± 9 | 60% | 6/20 (30%) |
| 45% | 20 | +0,2 ± 3,9 | 74 ± 9 | 55% | 6/20 (30%) |
| 50% | 20 | −0,8 ± 3,3 | 72 ± 7 | 49% | 8/20 (40%) |
| 75% | 20 | +0,1 ± 3,6 | 74 ± 8 | 25% | 4/20 (20%) |
| 100% | 1 | 0,0 | 0 | 0% | 0/1 |

O multi-semente **corrige** a leitura da figura de uma semente:

- **Só sem perda o benefício é confiável.** Com 0% de perda o lift é **+5,4 mV**
  (determinístico). Com **qualquer** perda relevante (25–75%) o lift médio
  **desaba para ~0** e o desvio entre sementes (±3,3 a 4,0 mV) é **maior que a
  média** — ou seja, o benefício é **estatisticamente indistinguível de zero** e
  o sinal de uma rodada para outra é aleatório. Não há "robusto até 25%": já em
  25% de perda o ganho confiável some. O "penhasco/limiar" da semente única era
  ruído.
- **A sobretensão noturna é real e intermitente.** Ocorre em **~20–45% das
  sementes** ao longo de toda a faixa 25–75% de perda (sem pico nítido), e
  **nunca** em 0% ou 100%. É a manifestação concreta do dado velho: Q de boost
  preso → sobre-injeção → V > 1,0 pu de madrugada.

## Conclusões

- **Comunicação boa (0% perda) ⇒ controle efetivo e confiável.** Lift +5,4 mV,
  ~87 kvar, **sem sobretensão**. Melhor caso.
- **Qualquer perda relevante (25–75%) ⇒ controle NÃO-CONFIÁVEL e ARRISCADO.** O
  benefício médio cai para ~0 com **alta variância** (ora ajuda, ora atrapalha) e
  surge **risco de sobretensão** (~20–45% das rodadas). Não existe ponto de
  operação "parcial" seguro: **com perda de pacotes não dá para confiar no
  controle**.
- **Sem comunicação (100% perda) ⇒ controle inerte.** `Q = 0`, **idêntico ao
  baseline** — e, por isso, **sem sobretensão**.

É a versão forte (e agora estatisticamente apoiada) da tese do projeto: **não
basta o controlador agir — ele precisa de informação a tempo e confiável**.
Comunicação degradada não dá um "meio-controle": ela torna o controle
**imprevisível e potencialmente danoso** antes de simplesmente pará-lo.

## Como reproduzir o multi-semente

```bash
./run_loss_multiseed.sh     # 7 níveis estocásticos × 20 sementes + det. (resumível)
docker compose run --rm --no-deps \
  -e MOSAIK_OUTPUT_DIR=/app/output/sensibilidade_perda_multiseed \
  mosaik python plot_loss_multiseed.py
```

Relacionado: a discussão fenomenológico × mecanístico do modelo de perda está em
[`INTEGRACAO.md`](INTEGRACAO.md#a-perda-de-pacotes-é-parâmetro-não-resultado).
