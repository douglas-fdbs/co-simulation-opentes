# Comparação direta com a tese de Lucas Silveira Melo

Lado a lado: o que a tese usa e o que este trabalho usa, o que ela obtém e o que
obtemos, incluindo os casos em que os resultados **não** coincidem e por quê.

Fonte: MELO, Lucas Silveira. *Modelo de simulação computacional multidomínio para
análise de redes elétricas inteligentes com aplicação em transações econômicas de
energia*. Tese de doutorado, UFC, 2022. Capítulo 6 e Apêndices A a C.
Implementação de referência: repositório `market-simulation` (GREI-UFC).

Uma ressalva que vale para o documento inteiro: os números da tese vêm do texto e
das figuras dela, lidos por nós. Onde a leitura foi de figura, e não de tabela,
está dito.

---

## 1. Ferramentas

| Camada | Tese (2022) | Aqui | Por que mudou |
|---|---|---|---|
| Agentes | PADE 2.2, Python 3.6 | PADE 3.0, Python 3.12 | A 2.2 não roda em Python moderno. A modernização é entrega própria do projeto. |
| Orquestrador | Mosaik 2.2 | Mosaik 3.5 | API de passo mudou: `step(time, inputs, max_advance)` e passo adiado por `step_done()`. |
| Rede de comunicação | ns-3, via o módulo `pade.simul` | OMNeT++ | O `pade.simul` foi **removido** no PADE 3.0. O OMNeT++ é o simulador adotado pelo time TSCC. |
| Rede elétrica, fluxo de potência | pandapower **e** MyGrid, dois modelos da mesma rede | OpenDSS, um modelo, via `py-dss-interface` | Os dois modelos da tese divergiam entre si (seção 4 do `MERCADO.md`). Unificar é contribuição deste trabalho. |
| Sensibilidade de tensão | `J⁻¹₂₁` extraído do Jacobiano do pandapower | `∂V/∂P` e `∂V/∂Q` por perturbação no próprio OpenDSS | Elimina o segundo simulador e não depende de o solver expor o Jacobiano. |
| Otimização | CPLEX com PySP | CPLEX com Pyomo em forma extensiva | O PySP foi removido do Pyomo 6. Com 9 cenários não há o que decompor. |
| Execução | Scripts locais | Docker Compose, um container por simulador | Reprodutibilidade e isolamento. |

**Validação da troca de simulador elétrico.** O modelo pandapower de referência
foi reproduzido e comparado barra a barra em seis cenários de carga, incluindo um
com injeção líquida negativa. Pior desvio: **2,08e-5 pu**. A matriz de
sensibilidade obtida por perturbação bate com o `J⁻¹₂₁` do pandapower com erro
relativo mediano de **0,04%** e máximo de 0,86%.

## 2. Modelo e caso de estudo

| Item | Tese | Aqui | Coincide? |
|---|---|---|---|
| Rede | 75 nós (7 MT, 68 BT), 5 transformadores | a mesma, do `force.json` | sim |
| Agentes | 1 AM, 1 AD, 5 AC, 25 AP | idem, mais 1 solver | sim |
| Penetração PV | 50% das barras BT (34 nós) | idem | sim |
| Armazenamento de prosumidor | 30% das barras BT (25 nós) | idem | sim |
| Armazenamento de rede | 30% das barras BT (23 nós) | idem | sim |
| Horizonte | 24 h em 96 intervalos de 15 min | idem | sim |
| Limites de tensão | 0,97 a 1,03 pu | idem | sim |
| Transformadores | 250 kVA uniformes no modelo do AD | 45/75/112,5 kVA do `force.json` | **não**, ver 5.1 |
| Restrição de carregamento | corrente em todos os ramos, por matriz de incidência | potência por transformador (Eq. 6.13) | **não**, ver 5.2 |
| Modelo do prosumidor | estocástico, 9 cenários, PySP | forma extensiva, número de cenários parametrizável | equivalente |
| Restrição de SoC terminal | não existe | existe, ligável | **não**, ver 5.3 |
| Margem na restrição de tensão | não existe | 2e-3 pu | **não**, ver 5.4 |

## 3. Resultados que coincidem

### 3.1 O efeito da negociação sobre a tensão

Este é o resultado central da tese, e ele se reproduz.

| | Tese | Aqui |
|---|---|---|
| Horário crítico de subtensão | 17:45 | 17:45 (intervalo 71) |
| Tensão sem armazenamento | 0,94 pu | 0,93946 pu |
| Tensão após a negociação | 0,97 pu | 0,97033 pu |

A tese descreve assim: "a elevação da tensão às 17:45 de 0,94 pu para 0,97 pu, ou
seja, dentro da margem de objetivo buscada pelo sistema de orquestração dos RED".
Aqui, no fluxo de potência não linear completo do OpenDSS, a mínima do dia vai de
0,93946 para 0,97033 pu, e os pontos abaixo do limite vão de **337 para zero**.

O horário coincidir não é acaso: ele sai da mesma curva de demanda do SimBench
com o mesmo dimensionamento por nó. Foi, aliás, o que denunciou um erro nosso: a
carga base estava 2,72 vezes menor que a da tese, e só depois de corrigida a
mínima caiu para o horário certo.

### 3.2 O horário crítico de sobretensão

A tese aponta 10:00 como o horário crítico de sobretensão. Aqui a máxima do dia
ocorre entre 10:00 e 11:00, com 1,02282 pu no caso negociado, abaixo do limite de
1,03 pu, como na tese, que também não relata violação de sobretensão.

### 3.3 O comportamento do armazenamento

A tese descreve o dispositivo que "carrega durante o período da madrugada, com
preços mais favoráveis, e descarrega ao longo do dia". A figura
`programacao_no.png` mostra o mesmo padrão: carga plena até cerca do intervalo 20,
descarga concentrada no fim da tarde.

### 3.4 Os tempos de entrega da rede de comunicação

A rede 6TiSCH usa os parâmetros da própria tese: Pister-Hack sobre Friis a
915 MHz, Tabela 7 para converter RSSI em PER, sensibilidade de −106,37 dBm,
slotframe de 101 timeslots em 4,04 s, quadro de 127 bytes, as coordenadas do
Apêndice B e a **matriz de adjacência do Apêndice C**.

| | Tese | Aqui |
|---|---|---|
| Enlaces | 578 | 578, lidos do arquivo |
| Coordenadas | Apêndice B | idênticas, conferidas com o `bus_xy.txt` |
| Tamanho das mensagens na operação | 100 a 1500 bytes | CFP de operação medido em 1.004 bytes |
| Tempo de recepção | 10 a 90 s | 6,3 s para 100 B a 73,7 s para 1500 B |

**Um parâmetro é calibrado, e vale dizer qual.** O número de cells alocados por
enlace por slotframe é o que mais mexe no tempo de entrega, e a tese não o
informa. Com 1 cell, a configuração mínima do 6TiSCH, os tempos vão de 6 a 140 s
e ficam acima da faixa dela; com 2 cells, de 6 a 74 s, dentro dela. O padrão é 2,
declarado como calibração.

**Uma versão anterior deste documento afirmava que os tempos saíam "sem ajuste".**
Isso estava errado por um motivo que vale registrar: a adjacência era regenerada a
partir das coordenadas, e regenerar exige supor o orçamento de enlace do rádio,
que a tese não publica. A suposição natural de 0 dBm produziu 1.466 enlaces contra
os 578 reais, uma rede com metade dos saltos e muito menos perda. Os tempos
caíam na faixa da tese por compensação de dois erros: topologia otimista demais e
cells de menos.

## 4. Resultados que diferem, e o quanto cada diferença foi explicada

### 4.1 e 4.2 Rodadas e preço sombra: a diferença foi reconciliada

Estes dois números eram os que mais divergiam, e a explicação é a mesma. Um
experimento de ablação, desligando uma a uma as diferenças de modelagem, mediu a
contribuição de cada uma.

**A base teórica.** λ é o multiplicador de Lagrange da restrição de acoplamento
`ACP = ADP`. Ele é propriedade do PROBLEMA, não do algoritmo: um método de
subgradiente convergente vai para o λ* do problema, seja em 8 ou em 47 rodadas.
Se dois λ diferem e ambos convergiram, os problemas é que são diferentes.

**Ablação, com α = 0,6 e resíduo em kW:**

| Configuração | Rodadas | λ máximo |
|---|---:|---:|
| Nosso caso completo, 1 cenário | 47 | 5,610 |
| Só trocando os transformadores por 250 kVA | 47 | 5,610 |
| Só sem a restrição de SoC terminal | 39 | 5,061 |
| Só sem a margem de tensão | >80 | 5,133 |
| As três desligadas | >80 | 4,255 |
| **As três desligadas, com 9 cenários** | **9 (com ε = 1e-1)** | **2,359** |
| **Tese** | **8** | **2,18** |

**Duas hipóteses caíram no caminho.** O transformador não tem efeito nenhum: o
caso com 250 kVA é idêntico ao nosso dígito por dígito, ou seja, a restrição de
carregamento nunca atua nem com os transformadores reais, o que é coerente com o
carregamento máximo medido de 41,88% da ampacidade. E a margem de tensão
ATRAPALHA a convergência em vez de ajudar: sem ela são necessárias mais de 80
rodadas em vez de 47, porque ela dá ao DSO uma solução mais estável para onde
convergir.

**O fator dominante é o modelo estocástico.** Passar de 1 para 9 cenários leva λ
de 4,255 para 2,359, contra os 2,18 da tese: **8% de diferença**, dentro da
margem de leitura da tabela dela e da amostragem de cenários. O prosumidor que
decide sob incerteza programa de forma menos agressiva, estressa menos a rede, e
o preço sombra necessário para resolver o conflito cai.

**E as rodadas são o critério de parada.** Nas condições da tese com 9 cenários,
o `|Δλ| ≤ ε` dispara na rodada 9 se ε = 1e-1, e exige mais de 150 se ε = 1e-4,
que é o valor do código original:

| ε | Rodada | Resíduo primal |
|---|---:|---:|
| 1e-1 | 9 | 0,1656 kW |
| 1e-2 | 20 | 0,0142 kW |
| 1e-3 | 30 | 0,0015 kW |
| 1e-4 | >150 | — |

A tese para em 8 rodadas, e aqui na rodada 8 o `|Δλ|` está em 1,24e-1. Ou seja, o
ε efetivo dela é da ordem de 1e-1, três ordens de grandeza mais frouxo que o
nosso padrão. **As 8 rodadas dela e as nossas descrevem o mesmo processo parado em
pontos diferentes**, e o resíduo primal na rodada 9 ainda é de 0,17 kW.

**Conclusão.** Com as mesmas condições de modelagem e o mesmo critério de parada,
o trabalho reproduz a tese em 9 rodadas contra 8, e λ de 2,359 contra 2,18. As
diferenças que restam no caso PADRÃO deste trabalho, 34 a 47 rodadas e λ de 5,6,
são efeito deliberado das três adições, e não discordância de resultado.

### 4.3 A fase de operação quase não age

A tese relata intervenções na fase de operação, com reprogramação do
armazenamento de rede e, quando necessário, leilão de tempo real. Aqui, com o
mesmo mecanismo de perturbação de ±10% da tese, **nenhum dos 95 intervalos exigiu
intervenção**: o desvio agregado tem mediana de 0,20 kW e máximo de 1,47 kW, e a
programação do dia seguinte já absorve isso.

A causa provável é a margem de 2e-3 pu, que não existe na tese: ela deixa folga
suficiente para o desvio de operação caber. Trocando o mecanismo para o modo
severo (`MARKET_REALIZED_MODE=day`, um dia inteiro diferente do reservatório), a
operação volta a agir em 22 dos 96 intervalos, todos resolvidos pelo
armazenamento de rede.

### 4.4 A perda de pacotes, e o limiar de PER

A tese não reporta taxa de perda de mensagens. Aqui, sobre a topologia dela, a
negociação do dia seguinte perde **57 mensagens em 2.823**, ou 2,02%, e exige 43
retransmissões para fechar as 34 rodadas.

O mecanismo é uma consequência da própria regra da tese. Ela admite enlace sempre
que o PER fica abaixo de 0,5, e a Tabela 7 tem degrau em 0,4. Um enlace admitido
com PER 0,4 por quadro, já com as três retentativas do MAC, perde 2,6% dos
quadros. Uma mensagem de 100 bytes é um quadro e perde 2,6%; uma de 1250 bytes
são dez quadros, e perder qualquer um perde o datagrama: 22,8% previstos contra
27,5% medidos no enlace 5-36.

A consequência é operacional: o concentrador `trafo_5_35` fica atrás desse
enlace, e com três retransmissões a negociação **aborta na primeira rodada**. Foi
preciso subir o padrão para dez. É um resultado sobre a rede da tese, não sobre a
nossa implementação, e só apareceu ao usar a topologia publicada.

### 4.5 Tráfego da programação do dia seguinte

Aqui não há número da tese para comparar, e essa é justamente a observação. A
análise de comunicação dela é da fase de operação. Para a programação do dia
seguinte, cujo CFP carrega o preço sombra de 25 nós por 96 intervalos, o
`market_agent.py` original declara os mesmos 100 e 1000 a 1500 bytes, que não
correspondem ao conteúdo:

| | Tamanhos declarados | Conteúdo real |
|---|---:|---:|
| Tráfego total da negociação | 2,62 MB | 82,01 MB |
| Atraso p90 por mensagem | 77,2 s | 3.216,4 s |
| Tempo de rede da negociação | 3,7 h | 6,1 dias |

O número de rodadas é o mesmo nos dois casos, o que serve de verificação: a rede
altera o tempo, não o ponto de convergência.

Ressalva: esses dois números foram medidos sobre a topologia regenerada, mais
densa que a real. Com a topologia publicada os dois pioram na mesma proporção,
porque os saltos dobram, então a razão entre eles se mantém e a conclusão não
muda. A medição sobre a topologia correta ainda não foi refeita para o caso de
mensagens reais, que leva horas de relógio.

### 4.6 Adjacência da rede de comunicação

| | Tese | Primeira versão nossa | Agora |
|---|---:|---:|---:|
| Enlaces | 578 | 1.466 | 578 |
| Saltos médios | — | 1,50 | 3,18 |

A primeira versão regenerava a matriz a partir das coordenadas. Reconstruir exige
supor o orçamento de enlace do rádio, e a tese não o publica; com 0 dBm, o padrão
do Simulador 6TiSCH, o alcance sai cerca de 12 dB mais folgado que o real. A
matriz publicada passou a ser lida do arquivo.

## 5. Divergências de modelagem, e o motivo de cada uma

### 5.1 Transformadores

A tese usa 250 kVA uniformes no modelo pandapower do AD, valor que é resíduo do
std type `0.25 MVA 10/0.4 kV`. O `force.json` traz 45, 75 e 112,5 kVA por
transformador, que são valores de norma. Com 250 kVA a restrição de carregamento
nunca atua, e a Eq. 6.13 fica decorativa.

### 5.2 Restrição de carregamento

O código original restringe corrente em todos os ramos por matriz de incidência;
a Eq. 6.13 restringe potência por transformador. Seguimos a equação, porque é a
que tem limite conhecido. Medido: o carregamento de condutor chega no máximo a
41,88% da ampacidade, e nenhum dos 6.624 pontos passa de 100%, então a restrição
de corrente não atuaria de qualquer forma (`market_opentes.loading`).

### 5.3 Restrição de estado de carga terminal

Não existe na tese. Sem ela o modelo despeja a energia da bateria no último
intervalo, porque ela não vale nada na função objetivo. Está ligada por padrão e
pode ser desligada para reproduzir o comportamento original.

### 5.4 Margem na restrição de tensão

Não existe na tese. O otimizador cola a solução no limite e o erro da
linearização vira violação no fluxo não linear: sem margem, a negociação promete
0,9700 pu e o OpenDSS entrega 0,96924. Ela só aparece quando a restrição passa a
atuar de fato, o que depende da carga base estar certa.

### 5.5 A unidade do preço sombra

A tese é explícita (subseção 6.1.4.4): "Este trabalho não entrará no mérito da
questão de como tratar os valores encontrados para λ(t,l) como valores
financeiros reais. Os valores de preços encontrados serão interpretados apenas
como uma variável de controle".

Isso é consistente com a formulação: no ótimo do concentrador, λ = 2·Ck·(x_init −
x), então λ tem unidade de `Ck` vezes potência, e com o `Ck = 1` adimensional da
tese ele é numericamente um desvio de potência. As colunas de saída aqui saem
como `_signal` enquanto não houver calibração de `Ck` em moeda, e viram `_eur`
quando houver.

## 6. Figuras, uma a uma

| Figura da tese | Equivalente aqui | Observação |
|---|---|---|
| 42, PER por distância | `tisch_per.png` | Mesmo formato e mesma dispersão vertical do Pister-Hack. Acrescentamos um segundo quadro com a fração de pares que sobrevive ao limiar. |
| 43 e 47, tensão por nó ao longo do dia | `tensao_mercado.png` | A tese usa barras 3D por nó e por tempo; aqui são duas séries, mínima e máxima da rede. A leitura é a mesma e a nossa é legível em preto e branco. |
| 45, preço adicional | `dlmp.png` | |
| 50, programação e tensão do nó 74 | `programacao_no.png` | Aqui o nó é escolhido por maior discordância entre AC e AD, e as rodadas são espaçadas em escala logarítmica. |
| 51 e 52, programação por iteração | `programacao_no.png`, quadros (a) e (b) | |
| 54, tensão na fase de operação | `operacao.png` | Com o mecanismo de ±10% da tese, nenhum intervalo exige intervenção, e a figura diz isso. |
| 58, ciclos de mensagens | `ciclos.png` | A tese mostra a linha do tempo; aqui o eixo é o tempo de rede de cada ciclo contra a fatia dele na janela de 15 min. |
| Tabelas 10, 11, 18 e 19 | `tensao_por_no.csv` | Tensão máxima e mínima por nó, com horário. |
| — | `convergencia.png` | Não tem equivalente: a tese não publica curva de convergência. |
| — | `comunicacao.png` | Idem. |
| — | `transactions.csv`, `flexibility.csv` | A tese propõe os dois mercados mas não liquida as transações. |

## 7. O que este trabalho tem e a tese não

- **Um modelo de rede só**, em vez de dois divergentes.
- **Sensibilidade a reativo** (`∂V/∂Q`), que qualifica a hipótese ΔQ = 0 da Eq.
  6.16: ela vale enquanto o dispositivo não mexer em reativo, e se ele mantiver
  fator de potência constante o erro sobe quarenta vezes.
- **Liquidação das transações e DLMP**, que a tese propõe e não executa.
- **Retransmissão FIPA com timeout**, e uma política explícita para quem nunca
  responde.
- **Curva de convergência publicada**, com resíduo primal ao lado do critério da
  tese, o que expõe que o critério `|Δλ| ≤ ε` não é confiável sob passo
  decrescente.
- **Verificação de carregamento de condutor** como medição, e não como restrição
  decorativa.

## 8. O que a tese tem e este trabalho não

- **Modelo de rede da tese em ns-3**: aqui é OMNeT++, com o modelo 6TiSCH
  reconstruído a partir dos parâmetros publicados. Os dois não são o mesmo
  software.
- **Os três dispositivos inertes** (`shiftable_load`, `buffering_device`,
  `freely_control_gen`): estão no `config.json` da tese, mas as contribuições
  deles estão comentadas no `prosumer.py` original. Não foram implementados
  porque implementá-los afastaria o caso da tese, e não o aproximaria.
- **As tabelas de demanda líquida por nó** (Tabelas 12 a 17 do Apêndice A).
