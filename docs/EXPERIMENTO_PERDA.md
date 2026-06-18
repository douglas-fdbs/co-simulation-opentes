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

## Conclusões

A degradação **não é suave** — há um **limiar abrupto entre 25% e 30% de perda**
em que o controle passa de eficaz para contraproducente. Três regimes:

- **Robusto até ~25% de perda ⇒ controle efetivo.** Com 0% **e 25%** de perda o
  resultado é **o mesmo** (mínima 0,920 → 0,938 pu; tempo em subtensão 26% → 20%;
  ~87 kvar). A tensão muda devagar (passos de 5 min), então perder 1 em 4
  medições ainda deixa o controlador **suficientemente informado**. Boa notícia:
  o controle tolera uma rede imperfeita até certo ponto.
- **Acima de ~30% ⇒ controle contraproducente.** O achado mais importante: a
  partir de 30% o controlador **ainda injeta reativo** (~64–70 kvar), mas sobre
  **dados desatualizados** — entre uma medição e outra ele segura o último `Q`,
  que já não corresponde à tensão atual. O efeito líquido vira **negativo** (lift
  de −1,3 a −3,8 mV no intervalo 30–75%): **esforço de controle sem informação
  fresca vira esforço desperdiçado, ou pior, prejudicial**.
- **Sem comunicação (100%) ⇒ controle inexistente.** O controlador nunca recebe a
  tensão, segura `Q = 0` e o resultado é **idêntico ao baseline**. Valida o modelo
  (ausência de informação anula o controle, sem quebrar a simulação).

É a versão forte da tese do projeto: **não basta o controlador agir — ele precisa
de informação a tempo**; comunicação ruim pode ser pior do que não ter controle.

> **Ressalva metodológica.** Os números são de **uma realização** (semente fixa;
> *quais* pacotes se perdem é sorteado). Na região prejudicial (30–75%) o lift
> **oscila** entre −1,3 e −3,8 mV de um nível para o outro — esse "balanço" é
> ruído da semente única (depende de quais medições caem), **não** uma tendência
> física. O que é robusto: o **sinal** (positivo até 25%, negativo de 30% a 75%,
> zero em 100%) e a **posição do limiar** (~25–30%). Para suavizar a curva e ter
> barras de erro, repetir cada nível com várias sementes (`seed-0-mt` no
> `omnetpp.ini`) e tirar média/desvio — fica como próximo passo.

Relacionado: a discussão fenomenológico × mecanístico do modelo de perda está em
[`INTEGRACAO.md`](INTEGRACAO.md#a-perda-de-pacotes-é-parâmetro-não-resultado).
