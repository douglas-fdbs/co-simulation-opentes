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

A rede 6TiSCH foi reconstruída a partir dos parâmetros da própria tese, sem
ajuste: Pister-Hack sobre Friis a 915 MHz, Tabela 7 para converter RSSI em PER,
sensibilidade de −106,37 dBm, enlace viável com PER abaixo de 0,5, slotframe de
101 timeslots em 4,04 s, quadro de 127 bytes, e as coordenadas do Apêndice B.

| | Tese | Aqui |
|---|---|---|
| Tamanho das mensagens na operação | 100 a 1500 bytes | CFP de operação medido em 1.004 bytes |
| Tempo de recepção | 10 a 90 s | mediana 23,7 s, máximo 96,4 s |

Os números caem sozinhos do modelo: 100 bytes cabem em um quadro e chegam em
cerca de 4 s; 1250 bytes ocupam 10 quadros e chegam em cerca de 77 s.

## 4. Resultados que diferem

### 4.1 Número de rodadas até a convergência

| | Tese | Aqui |
|---|---|---|
| Rodadas | 8 | 34 |

A tese afirma: "chegou-se, após 8 rodadas de interações de negociação".

O primeiro passo para comparar foi descobrir qual passo do subgradiente ela usa
de fato. O `alpha = 0.0005` do código original não converge no porte real, e a
diferença é de unidade: o resíduo que alimenta a Eq. 6.30 vem das mensagens ACL,
onde as potências trafegam multiplicadas por 1e3, ou seja em W, enquanto as
variáveis dentro dos modelos estão em kW. O passo efetivo da tese equivale a
**α = 0,5 com resíduo em kW**, e com esse valor a nossa negociação converge em 20
rodadas, não em 8.

O que explica o resto da diferença:

- A margem de 2e-3 pu na restrição de tensão, que não existe na tese, aperta a
  região viável: sozinha ela leva a convergência de 28 para 34 rodadas.
- Os transformadores de 45 a 112,5 kVA no lugar dos 250 kVA uniformes fazem a
  restrição de carregamento entrar no problema.
- O critério `|Δλ| ≤ ε` é um resíduo primal escalado pelo passo, então o mesmo ε
  significa coisas diferentes sob passos diferentes. Reportamos o resíduo primal
  ao lado, e é por ele que se deve comparar.

O passo α = 0,6 constante, aliás, converge para uma vizinhança e não para o
ótimo, com raio que cresce com α: acima de 0,65 nesta rede o raio ultrapassa a
tolerância e acima de 0,75 aparece ciclo limite.

Vale registrar o que isso custou descobrir: o teto de rodadas estava em 30, e a
negociação vinha sendo **cortada antes de convergir** sem que nada avisasse,
porque a programação entregue continuava factível e a tensão continuava dentro do
limite. O `converged=False` só apareceu quando o registro da execução passou a ser
gravado.

### 4.2 Magnitude do preço sombra

| | Tese (Tabela 8) | Aqui |
|---|---|---|
| λ máximo | 2,18, no nó 25 às 19:30 | 5,61 |
| λ típico | 0,01 a 1,05 | — |

Diferença esperada: λ é o acumulado do subgradiente, `λ ← λ + α·(x − y)`, então
depende de quantas rodadas se acumulou e de α. Com 34 rodadas contra 8, o valor
final é maior. Não é grandeza monetária em nenhuma das duas, ver 5.5.

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

### 4.4 Tráfego da programação do dia seguinte

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
