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

> ⚠️ **Resultados RE-RODADOS após DUAS correções (commits `ab0b04e` e `c63cc3a`,
> 2026-06-22):** (1) o **congelamento do solve** (`set_pvsystem_pq`) e (2) o
> **off-by-one nos LoadShapes**. A versão anterior desta seção concluía "ponto de
> quebra em ~5%", controle "não-confiável" e "sobretensão noturna" — tudo
> **artefato dos bugs**. As conclusões antigas estão **retratadas**.

Varredura de perda de **0% a 100% em passos de 5%**, cada nível com **20 sementes**,
agregando média ± desvio. Figura: `sensibilidade_perda_multiseed.png`.

| Perda | lift médio ± dp [mV] | Perda | lift médio ± dp [mV] |
|---:|---:|---:|---:|
| 0% | +0,3 (det.) | 55% | +1,7 ± 2,2 |
| 5% | +0,8 ± 1,4 | 60% | +2,4 ± 2,3 |
| 10% | +1,9 ± 2,2 | 65% | +1,0 ± 1,7 |
| 15% | +1,9 ± 2,2 | 70% | +1,4 ± 2,0 |
| 20% | +1,7 ± 2,2 | 75% | +1,7 ± 2,2 |
| 25% | +2,4 ± 2,3 | 80% | +0,9 ± 1,6 |
| 30% | +2,2 ± 2,3 | 85% | +2,0 ± 2,3 |
| 35% | +1,9 ± 2,2 | 90% | +1,9 ± 2,1 |
| 40% | +2,2 ± 2,3 | 95% | +2,0 ± 2,2 |
| 45% | +2,6 ± 2,3 | 100% | 0,0 (det.) |
| 50% | +1,2 ± 1,9 | | |

*(Q médio ≈ 60–69 kvar; Entregue% = 100 − perda%. **0 violações ANEEL** (V652 >
1,05 pu) em todos os níveis — máximo global ≈ 1,028 pu, ao meio-dia.)*

### Leitura corrigida (e uma ressalva importante de métrica)

- **O controle regula a tensão e é seguro em toda a faixa de perda**, sem violação
  ANEEL em nenhum cenário. O perfil diário ficou fisicamente coerente (sem picos
  espúrios; ver estudo de 48h).
- **Cuidado com o "lift da média":** ele **premia injeção de reativo, não
  regulação**. Em **0% de perda** o controle faz Volt/Var correto — **absorve**
  quando a tensão sobe (meio-dia, PV) e **injeta** quando cai (noite) — então o
  Q médio é negativo (−54 kvar) e o lift líquido fica pequeno (+0,3 mV), embora
  esteja **regulando bem**. Sob perda alta o controle **segura** um Q que por acaso
  injeta (+52 kvar em 95%), o que **infla a tensão média** (lift ~+2 mV) sem
  necessariamente regular melhor. Por isso o lift **não** decai com a perda como
  se esperaria — não é que a perda "ajude", é a métrica que engana.
- **Métrica mais honesta — redução do desvio-padrão da tensão** (quanto o controle
  *regula*): o controle reduz o desvio em **~7 a 11% em todos os níveis de perda**
  (baseline 0,0197 → ~0,0175–0,0185 com controle), **sem tendência clara** ao longo
  de 0–95%. Em **100%** (Q=0) não há regulação.

## Conclusões

- **O controle Volt/Var funciona e é seguro** (regula ~7–11% do desvio de tensão,
  sem violação ANEEL) em **toda a faixa de perda**.
- **Neste estudo de caso, a perda de comunicação NÃO degrada fortemente o
  benefício.** A tensão muda devagar (passos de 5 min) e o último Q válido
  "segurado" ainda regula de forma comparável — só em 100% (Q=0) o controle some.
- **As inconsistências apontadas eram artefatos de dois bugs** (solve congelado +
  loadshape), agora corrigidos; a física está coerente.

**Encaminhamento:** para um benchmark em que o impacto da comunicação **apareça com
clareza**, vale (a) usar uma métrica de **violação/regulação** em vez do lift da
média, e (b) tornar o caso mais exigente — dinâmica mais rápida, ganho mais
agressivo ou eventos de rede — de modo que a perda de pacotes realmente "morda".

## Estudo de 48h — o ciclo diário se repete

Para verificar a coerência temporal (o perfil diário deve **repetir** de um dia
para o outro), rodou-se o cenário em **horizonte de 48h** (2 dias com a mesma
irradiância), com o solve corrigido. Script: `run_48h.sh`; figura: `ciclo_48h.png`
(`output/sensibilidade_48h/`).

**Resultado:** o ciclo **fecha** — a tensão da barra 652 no dia 2 é **idêntica**
à do dia 1 (diferença de 0,0 mV hora a hora no baseline; no Volt/Var, idêntica
exceto **−1,4 mV apenas no passo 0**, o transitório de cold-start do solve). O
perfil é fisicamente coerente: ~0,976 pu à meia-noite → 1,025 pu ao meio-dia (PV)
→ **0,926 pu no pico de carga noturno (~21h)** → sobe de madrugada (carga caindo).

Isso resolve a inconsistência do "início ≠ fim do dia": o ~1,02 pu que aparecia no
começo era o **valor congelado** do solve; com a correção, o início (meia-noite)
casa com o dia seguinte. Resta apenas o transitório de **1 passo** no arranque
(antes eram ~31 passos / 2,5h).

**Correção adicional (bug de dados no loadshape):** o estudo de 48h também revelou
um **pico espúrio de tensão (~1,02 pu) no último ponto do dia** (23:50), presente
inclusive no baseline. Causa: em `LoadShape.dss`, as curvas `LoadShape1–8`
declaravam `npts=144` mas traziam **143 (ou 145) valores** — o OpenDSS preenchia o
144º ponto com **0,0** (carga zero às 23:50 → sobretensão momentânea). Corrigido
para que cada curva tenha exatamente `npts` valores. Erro herdado da base do TSRE;
afetava só os 2 últimos passos de cada dia (abaixo do limite ANEEL).

## Como reproduzir o multi-semente

```bash
./run_loss_multiseed.sh     # 7 níveis estocásticos × 20 sementes + det. (resumível)
docker compose run --rm --no-deps \
  -e MOSAIK_OUTPUT_DIR=/app/output/sensibilidade_perda_multiseed \
  mosaik python plot_loss_multiseed.py
```

Relacionado: a discussão fenomenológico × mecanístico do modelo de perda está em
[`INTEGRACAO.md`](INTEGRACAO.md#a-perda-de-pacotes-é-parâmetro-não-resultado).
