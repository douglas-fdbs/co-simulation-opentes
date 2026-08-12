# Revisão de cobertura contra a tese

O que do capítulo 6 da tese está implementado, o que está implementado de outro
jeito, e o que falta. Feita depois de fechar a Fase 6, varrendo as subseções
6.1.1 a 6.3.

Fonte: MELO, Lucas Silveira. *Modelo de simulação computacional multidomínio para
análise de redes elétricas inteligentes com aplicação em transações econômicas de
energia*. Tese de doutorado, UFC, 2022.

---

## 1. Coberto e validado

| Subseção | O que é | Onde está | Como foi validado |
|---|---|---|---|
| 6.1.1 | Dois ambientes de contratação, bilateral e spot | `optimization.solve_prosumer` | Reproduz as decisões do original |
| 6.1.2 | Quatro agentes (AP, AC, AD, AM) sobre PADE e FIPA | `market_agents.py` | Negociação distribuída bate com a centralizada |
| 6.1.3 | REDs: geração intermitente, armazenamento de prosumidor e de rede | `config.load_case` sobre o `config.json` original | Contagens conferem com a Tabela 6 |
| 6.1.4.1 | Otimização estocástica do prosumidor (Eq. 6.1 a 6.9) | `solve_prosumer` | Forma extensiva no lugar do PySP |
| 6.1.4.2 | Otimização do concentrador (Eq. 6.25 e 6.26) | `solve_concentrator` | — |
| 6.1.4.3 | Otimização do DSO (Eq. 6.12 a 6.17, 6.27 a 6.29) | `solve_dso` | Sensibilidade bate com `J⁻¹₂₁` a 0,04% |
| 6.1.4.4 | Decomposição dual e descoberta do preço sombra (Eq. 6.24 e 6.30) | `dual.py` e `MarketAgent` | Convergência caracterizada, incluindo o limite do critério de parada |
| 6.1.5 | Rede LPWA 6TiSCH | `comm-opentes/Tisch.cc` | Topologia do Apêndice C lida do arquivo; tempos na faixa da tese com 2 cells por slotframe, que é calibração declarada |
| 6.2.2 | Fase de programação da operação | Fluxo completo | 337 para ZERO pontos violados no fluxo não linear, com o mecanismo de demanda da tese |
| 6.2.3 | Fase de operação, dois níveis | `MarketAgent.start_operation` | Com o ±10% da tese nenhum intervalo exige intervenção; no modo severo, 22 tratados e todos resolvidos |

## 2. Implementado de outro jeito, com motivo

Os dez desvios conscientes estão na seção 3 do `MERCADO.md`. Os dois que mais
mudam número são a unificação dos modelos de rede em OpenDSS (seção 4) e a
sensibilidade por perturbação no lugar do Jacobiano do pandapower.

## 3. Lacunas encontradas nesta revisão

### 3.1 O desvio da demanda realizada é muito maior que o da tese

A tese (subseção 6.2.3) descreve o mecanismo assim: "um mecanismo de alteração
aleatória dos valores de demanda líquida dos prosumidores foi implementado
podendo alterar os valores programados anteriormente em até +/- 10%".

Aqui a demanda realizada é um DIA DIFERENTE do reservatório de perfis
(`MARKET_REALIZED_DAY=9`), não uma perturbação do dia programado. Medido: o
desvio agregado tem mediana de 9,4 kW e máximo de 51,2 kW, contra uma demanda
líquida agregada típica de 27 kW. Em ordem de grandeza é o dobro ou mais do que
±10% produziria.

Consequência: a fase de operação está sendo exercitada num regime bem mais duro
que o da tese, e os números das duas **não são comparáveis**. Não invalida nada
do que foi medido, mas invalida a comparação direta.

**Corrigido.** `MARKET_REALIZED_MODE=perturb` é agora o padrão e implementa o
mecanismo da tese; `day` continua disponível como caso severo. O ±10% é por
prosumidor e independente, então se cancela em 68 nós: o desvio agregado cai de
9,4 kW de mediana para 0,2 kW.

Efeito no fluxo não linear completo:

| Mecanismo | Sem negociação | Negociado |
|---|---|---|
| ±10% da tese | 0,93946 pu, 337 pontos violados | 0,97033 pu, **0 pontos** |
| dia alternativo | 0,94013 pu, 442 pontos violados | 0,96955 pu, 4 pontos |

Com o mecanismo da tese a negociação resolve tudo. Os 4 pontos residuais do outro
modo são o resíduo da linearização sob um desvio várias vezes maior.

### 3.2 A medição de comunicação foi feita na fase errada

Esta corrige uma conclusão que eu mesmo documentei na seção 5.1 do `MERCADO.md`.

A análise de comunicação da tese (subseção 6.2.3.1) é da **fase de operação**,
não da programação do dia seguinte. Na operação, a mensagem carrega um único
intervalo. Medido: o CFP de operação desta implementação tem **1.004 bytes**, que
cai exatamente dentro dos 1000 a 1500 bytes que o `market_agent.py` original
declara.

Ou seja, os tamanhos declarados na tese estão certos para a fase que ela mede, e
a análise de comunicação dela se sustenta. O que não se sustenta é usar os mesmos
100 e 1000 a 1500 bytes para a programação do dia seguinte, cujo CFP carrega 96
intervalos e chega a 27.275 bytes só no vetor de preço sombra e programações. A
tese não reporta resultados de comunicação para essa fase, então o problema fica
latente no código e não aparece nos resultados dela.

A medição da Fase 5 continua válida como resultado, com o escopo corrigido: ela
mostra que a programação do dia seguinte não cabe na rede LPWA com o conteúdo
real das mensagens. Ela **não** mostra que a análise de comunicação da tese
subestima o tráfego.

### 3.3 Os três ciclos, e um deles que não existia

A tese posiciona os três ciclos de troca de mensagens em instantes definidos
dentro da janela de 15 minutos: AC com seus AP no minuto 1, AD com os AC no
minuto 5, AM com AC e AD no minuto 10.

**O ciclo 2 não existia como tráfego.** O tratador de `REPORT` estava escrito no
concentrador, mas nenhum agente enviava o CFP correspondente: o agente de mercado
lia `p_init` direto da memória do concentrador, por dentro do processo. O atalho
pulava a rede inteira, e por isso o ciclo 2 não apareceu em nenhuma medição de
comunicação, inclusive nas da Fase 5.

**Corrigido.** Os três ciclos existem agora nas duas fases, com o AD iniciando o
ciclo 2 como a tese descreve. Na operação o ciclo 1 pede apenas o intervalo
corrente, que é a diferença que a tese aponta entre as fases: "as programações
enviadas pelos AP e AC são compostas apenas pelo valor programado para o próximo
intervalo de tempo".

Os minutos 1, 5 e 10 entraram como **orçamento de tempo de rede**, não como espera
de relógio. A negociação inteira acontece dentro de um passo do Mosaik, com o
relógio da co-simulação parado, então o que tem significado é se o tempo de rede
de cada ciclo cabe na fatia dele.

Medido sobre a 6TiSCH, com a topologia do Apêndice C e os tamanhos de mensagem
da tese:

| Ciclo | Fatia | Tempo de rede | Cabe? |
|---|---:|---:|---|
| 1, AC com seus AP | 240 s | 105,7 s | sim |
| 2, AD com os AC | 300 s | 53,4 s | sim |
| 3, AM com AC e AD | 300 s | 61,5 s **por rodada** | ver abaixo |

Nenhum ciclo estoura isoladamente. O aperto está no ciclo 3, que é iterativo: a
descoberta do preço sombra levou 34 rodadas, e a 61,5 s cada uma isso dá 35
minutos, contra uma fatia de 5. Na programação do dia seguinte não é problema,
porque há horas disponíveis. Na fase de operação, cujo ciclo 3 tem 300 s, **cabem
cerca de cinco rodadas**, e é esse o limite prático do leilão de tempo real sobre
esta rede.

A verificação de que a reestruturação não mexeu na física: o resultado elétrico
ficou idêntico, 337 pontos violados para zero, com mínima de 0,97033 pu.

### 3.4 Limite térmico de condutor

O AD da tese previne "ultrapassagem do limite térmico dos condutores e
transformadores". Aqui só o carregamento por transformador está implementado
(Eq. 6.13), e isso está registrado como desvio consciente número 5, porque é a
restrição da formulação e é a que tem limite conhecido. Fica anotado que a
descrição textual do agente é mais ampla que a formulação.

### 3.5 Saídas de resultado que a tese tem e nós não

**Corrigido**, em `market_opentes/plot_tese.py`. O que faltava antes não eram as
consultas, e sim os dados: o histórico e o registro da operação só existiam na
memória do agente e morriam com o processo. Agora a execução grava um
`data/run/run.json` com a programação que cada lado adotou por rodada e por nó.

| Saída | Equivalente na tese | Arquivo |
|---|---|---|
| Tensão máxima e mínima por nó, com horário | Tabelas 18 e 19 do Apêndice A | `tensao_por_no.csv` |
| Programação do AC e do AD por rodada, para um nó | Figuras 51 e 52 | `programacao_no.png` |
| Tempo de rede por ciclo contra a fatia dele | Figura 58 | `ciclos.png` |

Duas decisões de leitura que mudaram o que a figura diz. Na programação por nó,
as rodadas são espaçadas em escala logarítmica: o movimento da negociação
acontece quase todo nas primeiras rodadas, e quatro pontos equidistantes
deixariam três empilhados sobre a solução final. Na figura dos ciclos, a barra
que importa é a ACUMULADA: por execução o ciclo 3 gasta 91 s contra uma fatia de
300 s e parece folgado, mas ele se repete 28 vezes e soma 2.556 s.

O pior ponto de subtensão sai como nó 53, com 0,97033 pu às 16:30, coerente com
o horário crítico que a tese relata.

## 4. Fora do escopo por decisão da própria tese

HVAC e veículos elétricos: a subseção 6.1.3 os exclui explicitamente, por não
haver modelo de otimização que integre a dinâmica deles. Não são lacuna.

### 3.6 Defeitos encontrados durante a própria revisão

Três, todos corrigidos, e vale registrá-los porque nenhum se manifestava como
erro visível.

**A negociação vinha sendo cortada antes de convergir.** O teto de 30 rodadas era
herança de quando o `V_BACKOFF` era 1e-3; com a margem de 2e-3 da Fase 4 a região
viável aperta e a convergência passa a exigir 34. O resultado saía com
`converged=False` e nada avisava, porque a programação entregue continuava
factível. Teto para 60, com o vínculo entre os dois parâmetros registrado.

**O ciclo 2 não retransmitia.** Ao implementá-lo eu não repliquei o tratamento de
timeout que os ciclos 1 e 3 já tinham. Numa execução sobre a rede 6TiSCH o DSO
perdeu o relatório de um concentrador e desistiu, o que zera a flexibilidade de
todos os prosumidores sob ele. É a mesma lacuna do FIPA descrita na seção 5 do
`MERCADO.md`, reaberta por descuido.

**Figuras liam arquivos mortos.** A `operacao.png` lia um `operation_log.json`
que os agentes tinham deixado de escrever, e seguia desenhando dados antigos sem
erro nenhum, porque o arquivo velho continuava no disco. Agora cada execução
grava a própria configuração no `run.json` e as figuras saem carimbadas com ela,
para que procedência divergente fique visível em vez de silenciosa.

## 5. Pendências que já eram conhecidas

- Montar o IEEE European LV Test Feeder como caso principal citável; a MVLV75 é o
  caso de regressão.
- Reconciliar a documentação do cenário `integrated` com o comportamento atual.
- Decidir sobre a restrição de estado de carga terminal com o orientador.
- Rodar o `./run.sh market` completo sobre a rede 6TiSCH, e não só o teste
  isolado de negociação. Com mensagens reais isso hoje aborta por construção, ver
  a seção 5.1 do `MERCADO.md`; com os tamanhos da tese, completa.
