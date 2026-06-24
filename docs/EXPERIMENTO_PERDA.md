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

> ⚠️ **Resultados RE-RODADOS após a correção do solve (commit `ab0b04e`,
> 2026-06-22).** A versão anterior desta seção concluía haver um "ponto de quebra
> em ~5%", controle "não-confiável" e "sobretensão noturna" — tudo isso era
> **artefato do congelamento do solve** do OpenDSS (que afetava justamente o caso
> de 0% de perda). Com o solve corrigido, o quadro muda e fica coerente. As
> conclusões antigas estão **retratadas**.

Varredura de perda de **0% a 100% em passos de 5%**, cada nível com **20 sementes**
(`seed-0-mt` = 1..20, via `run_loss_multiseed.sh`), agregando média ± desvio. 0% e
100% são determinísticos. Figura: `sensibilidade_perda_multiseed.png`.

| Perda | lift médio ± dp [mV] | Perda | lift médio ± dp [mV] |
|---:|---:|---:|---:|
| **0%** | **+5,0** (det.) | 55% | +2,1 ± 2,3 |
| 5% | +0,5 ± 1,0 | 60% | +1,4 ± 2,0 |
| 10% | +2,6 ± 2,3 | 65% | +1,5 ± 2,1 |
| 15% | +1,7 ± 2,2 | 70% | +2,1 ± 2,3 |
| 20% | +2,2 ± 2,3 | 75% | +1,7 ± 2,2 |
| 25% | +1,5 ± 2,0 | 80% | +1,7 ± 2,1 |
| 30% | +1,7 ± 2,1 | 85% | +2,4 ± 2,3 |
| 35% | +1,5 ± 2,0 | 90% | +1,6 ± 2,1 |
| 40% | +1,9 ± 2,2 | 95% | +1,4 ± 1,9 |
| 45% | +1,7 ± 2,2 | **100%** | **0,0** (det.) |
| 50% | +2,4 ± 2,3 | | |

*(Q médio ≈ 60–69 kvar; Entregue% = 100 − perda%. Sobretensão ANEEL (V652 > 1,05
pu): **0 violações em todos os níveis** — máximo global ≈ 1,029 pu.)*

### Leitura corrigida

- **O controle AJUDA em toda a faixa de perda.** O lift é **positivo em todos os
  níveis** (e o desvio entre sementes caiu para ~±2 mV, contra ±3–4 antes — bem
  mais estável). Não há mais "ponto de quebra" nem comportamento "não-confiável":
  aquilo era o solve congelado.
- **O melhor caso é 0% de perda** (+5,0 mV). **Qualquer perda reduz o benefício**
  para ~+1,5 a +2,5 mV, mas ele **continua positivo** — e surpreendentemente
  **estável até 95%**: mesmo perdendo a maioria dos pacotes, o reativo "segurado"
  (último Q válido) ainda dá um suporte médio de tensão. Só em **100%** (nenhum
  pacote chega, Q=0) o controle zera.
- **Não há sobretensão acima do limite ANEEL** (1,05 pu) em nenhum cenário. A
  "sobretensão noturna" relatada antes era a tensão **naturalmente subindo de
  madrugada** (carga baixa → ~1,02 pu, dentro da norma), que o solve congelado
  mascarava — não um efeito do controle.

## Conclusões

- **Comunicação perfeita (0%) ⇒ melhor benefício** (lift +5,0 mV).
- **Comunicação degradada (5–95%) ⇒ benefício menor, porém positivo e estável**
  (~+2 mV). O controle **continua útil** mesmo sob perda alta, graças ao reativo
  segurado; a perda **atenua** o ganho, mas não o torna prejudicial.
- **Sem comunicação (100%) ⇒ controle inerte** (Q=0, = baseline).
- **Sem violação de tensão** (ANEEL) em nenhum caso.

Tese (revisada): a perda de comunicação **degrada gradualmente** o benefício do
Volt/Var distribuído (de +5 mV para ~+2 mV), mas o controle **permanece benéfico**
em toda a faixa — o melhor desempenho exige comunicação confiável, sem que a perda
parcial torne o controle perigoso.

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
