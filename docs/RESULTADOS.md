# Resultados da Co-simulação OpenTES — guia da pasta `output/`

Este documento explica, de forma didática, **tudo o que a co-simulação grava em
`output/`**: o que cada arquivo `.csv` significa (coluna a coluna, linha a
linha) e por que cada gráfico tem o comportamento que tem. A ideia é que
qualquer pessoa — mesmo sem conhecer o código — consiga ler os resultados.

> Conceito-base: o tempo avança em **passos de 5 minutos**. Um dia inteiro =
> **288 passos**. Cada **linha** dos arquivos de resultado é **um passo** (um
> instante do dia). A coluna `date` diz qual instante.

```
output/
├── integrated/   ← a co-simulação completa (A APLICAÇÃO): rede elétrica + comunicação
├── ieee13/       ← teste isolado da rede elétrica (sem comunicação)
└── star/         ← teste isolado da comunicação (sem rede elétrica)
```

---

## 1. `output/integrated/` — a co-simulação completa

É o cenário principal. Roda **duas vezes** e gera dois conjuntos de arquivos:

- sufixo **`_baseline`** → execução **SEM** controle (os inversores só injetam a solar);
- sufixo **`_volt_var`** → execução **COM** controle Volt/Var (os agentes regulam a tensão).

Comparar os dois é o experimento: *"o controle, decidido por agentes que recebem
a tensão pela rede de comunicação, melhora a operação da rede?"*

### 1.1. `result_baseline.csv` / `result_volt_var.csv` — o estado ELÉTRICO

São **288 linhas** (um dia) e **74 colunas**. A coluna `date` é o instante; as
demais se dividem em **6 grupos** (lidos da co-simulação a cada passo):

| Grupo de colunas | Quantas | Exemplo de coluna | O que é |
|---|---|---|---|
| **Tensão das barras** | 48 | `DSS-0.Bus-632-V1_pu` | Tensão em *por unidade* (1,0 = nominal) na barra `632`, fase 1. São 16 barras × 3 fases. Fases inexistentes (trecho monofásico) ficam ~0 e são ignoradas. |
| **P_dc dos painéis** | 5 | `PVSimulator-0.PVPanel_0-P_dc` | Potência **ativa disponível** (corrente contínua) que o painel solar entrega ao inversor, em kW. Depende da irradiância. |
| **P_ref dos controladores** | 5 | `PadeSim-0.AgenteB_1-P_ref` | Potência **ativa** que o agente **mandou** o inversor injetar (kW). Aqui = a solar disponível. |
| **Q_ref dos controladores** | 5 | `PadeSim-0.AgenteB_1-Q_ref` | Potência **reativa** que o agente decidiu (kvar) — a "alavanca" do Volt/Var. No baseline é sempre 0. |
| **P_meas dos PVs** | 5 | `DSS-0.PVSystem-pv1-P_meas` | Potência **ativa medida** nos terminais do inversor pelo OpenDSS (kW) — o que de fato entrou na rede. |
| **Q_meas dos PVs** | 5 | `DSS-0.PVSystem-pv1-Q_meas` | Potência **reativa medida** pelo OpenDSS (kvar). |

> Por que `P_ref` (mandado) pode diferir de `P_meas` (medido)? `P_ref` é o
> **setpoint** que o agente comanda; `P_meas` é o que o OpenDSS realmente injeta
> após resolver o circuito (limites do inversor e do modelo elétrico). É normal
> haver diferença.

#### Lendo linha a linha (exemplos reais do `result_volt_var.csv`)

**Linha da meia-noite** (`date = 2026-01-01`, passo 0):

```
P_dc = 0   |  P_ref = 0   |  Q_ref = 0   |  P_meas = 0   |  V ≈ 1,00 pu
```

*Interpretação:* **sem sol**, o painel não gera (`P_dc = 0`), então o inversor
não injeta nada e o agente não tem o que controlar (`Q_ref = 0`). A rede está
quase no nominal (~1,0 pu), só com a carga noturna.

**Linha do meio-dia** (passo ~144):

```
P_dc = 1022 kW  |  P_ref = 1022 kW  |  Q_ref = 0 kvar  |  P_meas = 682 kW
```

*Interpretação:* **com sol**, o painel entrega 1022 kW; o agente repassa essa
ativa (`P_ref = P_dc`) e, como a tensão daquela barra está **dentro da faixa
morta** (0,98–1,02 pu), ele decide `Q_ref = 0` (não precisa corrigir). O OpenDSS
injeta 682 kW na rede (`P_meas`).

**Quando o Volt/Var atua:** numa barra subtensionada (ex.: Bus 652, que chega a
0,92 pu), o agente da barra calcula um `Q_ref > 0` (injeta reativo) para
**levantar** a tensão; numa barra acima de 1,02 pu ele calcula `Q_ref < 0`
(absorve reativo) para **baixar**. É esse número que diferencia o
`result_volt_var.csv` do `result_baseline.csv`.

### 1.2. `comm_trace_baseline.csv` / `comm_trace_volt_var.csv` — o estado da COMUNICAÇÃO

Aqui mora a prova de que **a tensão trafega pela rede OMNeT++**. O formato é
"longo": **4 colunas** (`Tempo, Origem, Atributo, Valor`) e ~2304 linhas (288
passos × 8 atributos). `Origem` é sempre o nó da rede (`OmnetSim-0.node_0`).

Cada passo registra **8 atributos** (a coluna `Atributo` diz qual; `Valor`
guarda o dado):

| Atributo | O que é | Como ler |
|---|---|---|
| `val_out` | As **mensagens FIPA-ACL** que saíram da rede naquele passo | Texto JSON, várias mensagens separadas por `\|\|\|` |
| `packets_sent` | Total acumulado de pacotes **enviados** | Número |
| `packets_received` | Total acumulado **entregues** | Número |
| `packets_dropped` | Total acumulado **perdidos** | Número |
| `latencies_out` | **Latência** de cada pacote do passo (s) | Lista separada por `\|\|\|` |
| `jitters_out` | **Jitter** (atraso extra aleatório) de cada pacote (s) | Lista separada por `\|\|\|` |
| `packet_sizes_out` | **Tamanho** de cada pacote (bytes) | Lista separada por `\|\|\|` |
| `status` | Estado do nó (`idle`/`ok`) | Texto |

#### Exemplo de uma mensagem (`val_out`, passo t=600 s = 00:10)

```json
{"sender": "AgenteA_2", "bus": "632", "ontology": "medicao_tensao",
 "conversation_id": "meas-632-t600", "V_meas": 0.963648, "t": 600}
```

*Interpretação, palavra por palavra:* o medidor **`AgenteA_2`** leu a tensão da
barra **`632`** e mediu **`V_meas = 0,9636 pu`** no instante **`t = 600 s`**.
Essa carta entrou na rede OMNeT++, sofreu latência/jitter (e pode ter sido
descartada), e — se chegou — o controlador da barra 632 (`AgenteB_2`) a leu e
calculou o reativo. **É essa carta, com a tensão real lá dentro, que liga os
dois mundos.**

> Como verificar a integridade: pegue o último `packets_sent` e o último
> `packets_dropped`. No nosso caso, **730 enviados, 136 perdidos (18,6%)** — esse
> é o efeito do parâmetro `drop_probability = 0,15` do modelo de rede.

### 1.3. `dashboard_integrated.png` — o resumo visual (8 quadros)

O painel junta os dois domínios. Abaixo, **o que cada quadro mostra e por que ele
se comporta assim**:

**1) Irradiância solar (5 PVs).** Curva em sino: **zero à noite**, sobe após o
nascer do sol (~6h), **pico ao meio-dia/início da tarde**, cai até zerar no
pôr do sol (~18h). As 5 curvas diferem um pouco porque vêm de **dados reais**
(dataset BR-PVGen) — há nuvens e ruído.

**2) Temperatura dos módulos (5 PVs).** Acompanha a irradiância **com atraso**:
os módulos esquentam *depois* que o sol bate, então o pico de temperatura vem
**um pouco depois** do pico solar e cai devagar à tarde. Por isso a curva é
"empurrada para a direita" em relação ao quadro 1.

**3) Geração fotovoltaica agregada.** Duas linhas: **Σ disponível** (tracejada =
irradiância × potência nominal dos 5 PVs) e **Σ P_meas injetado** (o que de fato
entrou na rede). Ambas seguem o sol (zero à noite, pico ~4–5 MW à tarde). A
injetada fica **abaixo** da disponível por causa de eficiência do inversor e
limites do circuito.

**4) Tensões nas 13 barras (p.u.).** À noite ficam próximas de 1,0 (carga leve,
sem PV). Durante o dia, a **injeção dos PVs tende a levantar** as barras, e a
**carga tende a baixar** — o equilíbrio varia por barra: as **mais distantes da
subestação** (ex.: 652, 611) afundam mais (subtensão); a barra da **fonte (650)**
fica colada em 1,0. As linhas pontilhadas marcam os limites ANEEL (0,95–1,05).

**5) Integridade dos pacotes (pizza).** Mostra **entregues × dropados** no dia.
No nosso caso **81,4% entregues / 18,6% dropados** — reflexo direto do
`drop_probability` do modelo de rede. (Ver discussão sobre esse parâmetro em
[`INTEGRACAO.md`](INTEGRACAO.md#a-perda-de-pacotes-é-parâmetro-não-resultado).)

**6) Latência exata por pacote.** Cada ponto é **um pacote**: o eixo Y é o atraso
em ms (32–451 ms aqui). A nuvem de pontos sobe quando há **mais pacotes
competindo** pela banda no mesmo instante (mais fila → mais latência).

**7) Jitter distribuído.** O **atraso extra aleatório** de cada pacote (média
~50 ms). É o que torna a chegada das mensagens **irregular** — duas medições
seguidas podem chegar com espaçamentos diferentes. Espalhamento é esperado:
é estocástico por natureza.

**8) Efeito Volt/Var nas 5 barras PV.** Para cada barra controlada, a linha
**pontilhada** é o baseline (sem controle) e a **sólida** é com Volt/Var; a
faixa cinza é a zona morta. Onde a sólida está **mais próxima de 1,0 / mais
"puxada para dentro"** que a pontilhada, o controle **regulou** a tensão. O
efeito é maior na barra mais crítica (652): a mínima sobe de **0,920 → 0,938 pu**.

### 1.4. Figuras dedicadas de comparação e análise

Além do dashboard de 8 quadros, há duas figuras **focadas** (mais legíveis para
a apresentação), geradas por `plot_comparacao.py`:

**`comparacao_volt_var.png` — o controle atuando × não atuando.** É a resposta
direta a "qual a diferença, em p.u., do Volt/Var ligado vs desligado":

- *Linha de cima* — um quadro por barra PV (646, 632, 634, 645, 652). Em cada um,
  a curva **vermelha tracejada** é SEM controle e a **verde sólida** é COM
  Volt/Var. A faixa cinza é a zona morta; a linha pontilhada inferior é o limite
  ANEEL (0,95 pu). Onde a verde está **acima** da vermelha, o controle deu
  **suporte de tensão** (injetou reativo e levantou a barra subtensão).
- *Embaixo, à esquerda* — **desvio-padrão (σ) da tensão por barra**, vermelho
  (sem) vs verde (com). Barra verde mais baixa = tensão **menos oscilante** =
  controle regulando. **↓ é melhor.**
- *Embaixo, ao centro* — **tensão mínima do dia por barra**. Barra verde mais
  alta = o controle **tirou a barra do fundo do poço** (afastou da subtensão).
  **↑ é melhor.**
- *Embaixo, à direita* — resumo: **σ médio −10%** (0,0248 → 0,0224 pu) e a mínima
  crítica do Bus 652 subindo **0,920 → 0,938 pu**, sem criar sobretensão.

> Por que o efeito é "modesto"? O ganho é **propositalmente suave**
> (`Q_MAX_PCT = 0,05`). Com 5 inversores agindo juntos sob atraso/perda de rede,
> um ganho agressivo desestabiliza (chegou a ~1,12 pu nos testes). O valor da
> figura é mostrar que, mesmo suave, o controle **mede melhora consistente** em
> todas as barras — e que comunicação ruim limita o quão agressivo dá para ser.

**`analise_comunicacao.png` — caracterização da rede de comunicação.** Quatro
quadros que descrevem a **qualidade do canal** que o controle enfrenta (é a
mesma rede no baseline e no Volt/Var — mesma semente —, então caracterizamos uma
execução, não comparamos as duas):

- *Histograma de latência* — distribuição do atraso de entrega. Concentrado nos
  valores baixos com **cauda à direita** (média ~81 ms): a maioria chega rápido,
  alguns poucos demoram muito (fila/congestionamento momentâneo).
- *Histograma de jitter* — distribuição do atraso aleatório extra. Média ~53 ms,
  **coerente com o parâmetro** `jitter_mean = 0,05 s` do modelo — ou seja, a
  figura **valida** que o OMNeT++ está aplicando o atraso configurado.
- *Pizza de integridade* — dos **730** pacotes enviados, **594 entregues
  (81,4%)** e **136 dropados (18,6%)**. Reflete o `drop_probability = 0,15`
  (a perda observada flutua em torno dos 15% por ser **estocástica**).
- *Pacotes acumulados* — três linhas no tempo: **enviados** (azul, sobe até 730),
  **entregues** (verde = enviados − dropados) e **dropados** (vermelho). O **vão
  entre a azul e a verde é exatamente a perda** acumulada ao longo do dia.

> Detalhe de leitura: no `comm_trace`, `packets_received` espelha `packets_sent`
> (todo pacote "chega" ao nó e o descarte é marcado à parte). Por isso o
> **entregue real** é sempre `enviados − dropados`, e é assim que a figura conta.

---

## 2. `output/ieee13/` — teste isolado da rede elétrica

Roda **só** a rede (OpenDSS + 5 PVs + inversores), **sem** comunicação nem
agentes. Serve para **validar a física** contra o trabalho de referência do TSRE.

- **`result_run_ieee13_cosim_pv_5min.csv`** — mesmas grandezas elétricas
  (tensões, P/Q dos PVs), 288 passos. Reproduz **exatamente** os valores do
  Paulo Victor (pico `P_dc ≈ 3024,6 kW`, `P_ac ≈ 2854,2 kW`, `P_meas ≈ 1902,7 kW`).
- **`ieee13_dashboard.png`** — 4 quadros: irradiância, geração (P_dc e P_meas),
  tensões das barras e temperatura.

Use este cenário quando quiser conferir se uma mudança quebrou a parte elétrica:
se os números aqui ainda baterem com a referência, a física está intacta.

---

## 3. `output/star/` — teste isolado da comunicação

Roda **só** a comunicação (50 agentes PADE conversando em estrela via OMNeT++),
**sem** rede elétrica. É a bancada para estudar a rede de comunicação sozinha.

- **`results.csv`** — formato `Tempo, Origem, Atributo, Valor` (igual ao
  `comm_trace`), com a telemetria de rede e as mensagens trocadas.
- **`grafico_trafego.png`** — dashboard de tráfego: latência, jitter, tamanho de
  pacote e a **pizza de integridade** (entregues/dropados). É a referência visual
  que o quadro 5 do dashboard integrado reaproveita.

---

## Como gerar/atualizar os gráficos

```bash
# dashboard do cenário integrado (após ./run_opentes.sh integrated)
docker compose run --rm --no-deps -e MOSAIK_OUTPUT_DIR=/app/output/integrated \
  mosaik python plot_integrated.py

# figuras dedicadas: comparacao_volt_var.png + analise_comunicacao.png
docker compose run --rm --no-deps -e MOSAIK_OUTPUT_DIR=/app/output/integrated \
  mosaik python plot_comparacao.py

# dashboard do ieee13 isolado (após ./run_opentes.sh ieee13)
docker compose run --rm --no-deps mosaik python plot_ieee13.py
```

Os números e observações consolidados (efeito do controle, estabilidade,
parâmetro de perda) estão em [`INTEGRACAO.md`](INTEGRACAO.md#resultados).

---

## Experimento: sensibilidade à perda de pacotes

O estudo do **impacto da qualidade da comunicação** sobre o controle distribuído
(varredura de perda **0→100% em passos de 5%**, **20 sementes/nível**) tem doc
própria: [`EXPERIMENTO_PERDA.md`](EXPERIMENTO_PERDA.md). Roda com
`run_loss_multiseed.sh` e gera `sensibilidade_perda_multiseed.png`. Achado central
(**re-rodado após 2 correções — solve `ab0b04e` + loadshape `c63cc3a`**): o controle
**regula e é seguro em toda a faixa de perda** (reduz o desvio de tensão ~7–11% em
todos os níveis; **sem violação ANEEL**). Neste caso, a perda **não degrada
fortemente** o benefício (tensão muda devagar + Q segurado regula); só em 100% (Q=0)
some. Ressalva: o "lift da média" engana (premia injeção, não regulação). A leitura
antiga ("ponto de quebra", "não-confiável", "sobretensão") era **artefato dos bugs**.
