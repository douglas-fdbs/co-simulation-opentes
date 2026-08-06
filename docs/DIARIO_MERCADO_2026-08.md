# Diário de trabalho: a camada de mercado transativo

Registro detalhado da sessão de 4 e 5 de agosto de 2026, em que a camada de
mercado transativo da tese de doutorado de Lucas Silveira Melo foi portada para o
stack do OpenTES. O documento segue a ordem em que as perguntas foram feitas, e
registra tanto o que foi decidido quanto o que foi descartado e por quê. Serve
para análise posterior, não como resumo executivo.

Interlocutores: Douglas Barros (autor do TCC) e o assistente.
Repositório: `co-simulation-opentes`, branch `mercado-transativo`.

---

## Sumário

1. [Ponto de partida e primeira pergunta](#1-ponto-de-partida-e-primeira-pergunta)
2. [O levantamento dos dois repositórios](#2-o-levantamento-dos-dois-repositórios)
3. [As três decisões travadas](#3-as-três-decisões-travadas)
4. [A leitura da tese](#4-a-leitura-da-tese)
5. [Fase 1: a rede em OpenDSS](#5-fase-1-a-rede-em-opendss)
6. [Fase 2: a matriz de sensibilidade](#6-fase-2-a-matriz-de-sensibilidade)
7. [A pergunta sobre o CPLEX e o modelo estocástico](#7-a-pergunta-sobre-o-cplex-e-o-modelo-estocástico)
8. [Fase 3: os modelos e a decomposição dual](#8-fase-3-os-modelos-e-a-decomposição-dual)
9. [Fase 4: os agentes PADE](#9-fase-4-os-agentes-pade)
10. [Fase 5: a camada de comunicação](#10-fase-5-a-camada-de-comunicação)
11. [Fase 6: a fase de operação](#11-fase-6-a-fase-de-operação)
12. [Fase 7: as figuras](#12-fase-7-as-figuras)
13. [Revisão final](#13-revisão-final)
14. [Inventário do que foi criado e alterado](#14-inventário-do-que-foi-criado-e-alterado)
15. [Achados, por ordem de importância](#15-achados-por-ordem-de-importância)
16. [O que fica em aberto](#16-o-que-fica-em-aberto)

---

## 1. Ponto de partida e primeira pergunta

O pedido inicial foi construir um modelo de simulação computacional multidomínio
para análise de redes elétricas inteligentes com aplicação em transações
econômicas de energia, melhorando a implementação da tese do orientador. O
material disponível era:

- `co-simulation-opentes`, com quatro containers funcionais (`comm` em OMNeT++,
  `pade` em PADE 3.0, `mosaik` como orquestrador e `grid` em OpenDSS via
  py-dss-interface), tendo o IEEE 13 Barras como benchmark e um laço Volt/Var
  causal já funcionando;
- `market-simulation`, a implementação da tese, em PADE 2.2 com ns-3, pandapower,
  MyGrid, CPLEX e PySP;
- as anotações da reunião de 22 de julho de 2026 com o orientador.

Foram pedidas cinco coisas: definir a estrutura final em etapas, usar a reunião
como base de entendimento, escolher uma rede de teste adequada, encontrar onde
encaixar o `market-simulation` filtrando o que reaproveitar, e adotar uma postura
de revisor técnico rigoroso em vez de concordância automática.

**Registro honesto do primeiro turno**: a tese e os slides foram mencionados como
anexos mas não chegaram na conversa. Isso foi dito explicitamente antes de
qualquer análise, e a primeira rodada de conclusões foi construída lendo o código
do `market-simulation`, não a formulação da tese. Os dois PDFs chegaram depois e
foram lidos na íntegra.

## 2. O levantamento dos dois repositórios

A leitura do código produziu seis restrições duras, todas verificadas linha a
linha, que determinaram todo o desenho posterior:

**2.1 O `market-simulation` inteiro fala Mosaik 2.** Todos os cinco agentes
declaram `'api_version': '2.2'` e implementam `step(self, time, inputs)` sem
`max_advance`. O `co-simulation-opentes` roda Mosaik 3.5.0. Toda subclasse
`MosaikCon` precisaria ser portada. O driver novo já suporta o padrão assíncrono
de que o mercado depende, em que o `step` devolve `None` e o `step_done` é
chamado quando o protocolo FIPA terminou.

**2.2 A granularidade de simulador é oposta nos dois repositórios.** O
`market-simulation` sobe um simulador Mosaik por agente, cada um numa porta TCP a
partir de 1234: 68 prosumidores mais 5 concentradores mais DSO mais mercado,
setenta e cinco simuladores. O `co-simulation-opentes` sobe um processo PADE com
N agentes e um único `MosaikCon`, com os agentes num dicionário global.

**2.3 O `pade.simul` não existe mais no PADE 3.0.** No PADE 2.2 do orientador
existe um `SimulAgent` que intercepta toda mensagem ACL quando o agente roda com
`mode='simulation'`, empacota remetente, destinatário, `message_length` e
instante, manda para o servidor ns-3 por socket e recebe de volta o instante de
entrega. No PADE 3.0 esse módulo inteiro foi removido e o `send()` vai direto
para `reactor.connectTCP`. Não existia caminho pelo qual mensagens FIPA nativas
atravessassem o OMNeT++.

**2.4 O ContractNet do PADE não tem timeout.** `handle_all_proposes` só dispara
quando `received_qty == cfp_qty`, e a linha que armaria o timeout está comentada,
tanto na versão 3.0 quanto na 2.2. Com perda de pacotes, uma proposta perdida
travaria a rodada e, como o `step_done` sai de dentro do handler, travaria também
o Mosaik.

**2.5 O modelo do DSO depende do Jacobiano interno do pandapower.** A restrição
de tensão é linearizada como `ΔV = -J⁻¹₂₁ · ΔP`, com `J` extraído de
`net['_ppc']['internal']['J']`. O OpenDSS não expõe Jacobiano.

**2.6 O `api_opendss` não aceitava carga vinda do Mosaik.** O `step()` processava
entradas de `RegControl`, `Storage` e `PVSystem`, mas as cargas eram atualizadas
apenas pela `LoadShape` interna. O modelo `Load` declarava atributos que ninguém
lia. Nenhum agente conseguiria injetar demanda na rede.

Além disso: o solver era CPLEX em todos os modelos, e o modelo estocástico do
prosumidor usava `pyomo.pysp`, removido do Pyomo 6.

## 3. As três decisões travadas

Três escolhas mudavam materialmente o trabalho e foram levadas a decisão.

**Rede de teste.** O IEEE 13 foi descartado pelo motivo certo: tem nove cargas
agregadas em média tensão, nenhuma estrutura de transformadores secundários e
nenhum ponto onde faça sentido pendurar cinquenta prosumidores. Foram avaliadas
quatro opções: converter o `force.json` da tese, o IEEE European LV Test Feeder,
o EPRI Secondary Test Circuit e uma composição. A decisão foi **converter o
`force.json` como caso de regressão comparável e adotar o feeder europeu como
caso principal citável**. O argumento é metodológico: um TCC que afirma ter
melhorado uma implementação precisa de um caso onde a implementação nova e a
antiga rodem o mesmo sistema, senão não há como distinguir "melhorou" de "mudou a
rede".

**Comunicação.** Duas alternativas: recriar o `pade.simul` como shim PADE para
OMNeT++, preservando os protocolos FIPA, ou decompor a negociação em rodadas
mediadas pelo Mosaik, o que descartaria os protocolos do orientador. A decisão
foi o **shim**.

**Escopo.** Só a fase de programação (dia seguinte), deixando a fase de operação
em tempo real fora, como o próprio orientador havia sinalizado na reunião. Essa
decisão foi revista mais tarde, quando a Fase 6 foi pedida.

## 4. A leitura da tese

Com os PDFs em mãos, duas suspeitas levantadas na primeira análise foram
verificadas, e uma delas caiu.

**O termo lagrangiano assimétrico não é erro, é a formulação.** A Equação 6.25 dá
o objetivo do concentrador com sinal positivo em λ e a 6.27 dá o do DSO com sinal
negativo. O código implementa exatamente isso. A observação foi retirada.

**O critério de parada por |Δλ| é o da tese.** A Equação 6.30 e o texto dizem que
o agente de mercado reinicia a rodada enquanto `|λω − λω+1| ≤ ε` não for
respeitado. A crítica metodológica continua de pé, porque testar só o incremento
de λ com α pequeno pode declarar convergência com as programações ainda
descasadas, mas ela é sobre a tese, não sobre a implementação.

A leitura ainda fixou os parâmetros do estudo de caso: limites de tensão de 0,97
a 1,03 pu, penetração de 50% de PV e 30% de armazenamento de prosumidor e de
rede sobre as barras de baixa tensão, horizonte de 24 h em 96 intervalos, e
convergência em 8 rodadas. Os números do `config.json` batem: 34 nós com geração
em 68, exatamente os 50%.

Também decodificou os números mágicos dos agentes: os `SCHEDULE_TIME` de 0, 5 e
10 minutos são os três ciclos de troca de mensagens dentro da janela de 15
minutos.

E revelou o ponto que mais muda o trabalho: **a rede de comunicação da tese é
LPWA 6TiSCH**, sobre IEEE 802.15.4e a 50 kbps, com PER derivado do modelo de
propagação Pister-Hack em função da distância. Os resultados medidos são
mensagens de 100 a 1500 bytes e tempos de recepção de 10 a 90 segundos. O modelo
atual do `comm-opentes` tem a mesma taxa de 50 kbps, provavelmente herdada do
mesmo estudo, mas com perda plana de 15% e latência na casa de dezenas a
centenas de milissegundos.

## 5. Fase 1: a rede em OpenDSS

Foi escrito `grid-opentes/src/simulators/gen_market_grid.py`, que lê o
`force.json` e emite o circuito OpenDSS `src/data/MVLV75/`: 75 barras (7 em média
tensão e 68 em baixa), 69 linhas, 5 transformadores e 74 cargas.

**Validação.** O modelo pandapower de referência foi reproduzido fielmente e a
tensão comparada barra a barra em seis cenários de carga, incluindo um com
injeção líquida negativa para exercitar fluxo reverso. Pior desvio em toda a
bateria: **2,08e-5 pu**, ou 0,002%. Isso é ruído numérico entre dois solvers, não
diferença de modelo.

Um sinal de consistência: o caso base do próprio `force.json`, com soma de 67,3
kW e cerca de 1 kW por prosumidor, dá tensão mínima de 0,9579 pu, logo abaixo do
limite inferior de 0,97 pu da tese. A rede convertida cai exatamente no regime de
operação que motiva a negociação, sem ajuste.

**Três coisas que custaram tempo e ficaram documentadas no gerador:**

1. **O OpenDSS não aceita `Z0 == Z1`.** A primeira versão espelhava a sequência
   zero na positiva, já que o pandapower é de sequência positiva e as cargas são
   equilibradas. O resultado foi `Matrix Inversion Error` em todas as linhas: a
   montagem do Yprim a partir das componentes simétricas divide pela diferença
   entre elas. Vale igualmente para a fonte, com `MVAsc1 == MVAsc3`. Adotou-se
   R0 = 3·R1, X0 = 3·X1, C0 = 0,5·C1, relação típica de linha aérea, e `MVAsc1`
   5% acima de `MVAsc3`.
2. **As cargas precisam de `Vminpu`/`Vmaxpu` alargados.** Com o padrão de
   0,95/1,05 o OpenDSS troca o modelo de carga para impedância constante fora da
   faixa, e como a rede opera abaixo de 0,96 pu a comparação com o pandapower
   quebraria. Usou-se 0,7/1,4.
3. **O `py-dss-interface` não funciona no host.** Toda inversão de Yprim falha,
   inclusive no IEEE 13 que já existia. Dentro do container `opentes/grid:local`
   tudo compila e converge.

**Descoberta sobre a rede original.** O `market-simulation` descreve a mesma rede
em dois modelos incompatíveis: o pandapower usado pelo DSO tem transformadores de
250 kVA com vk = 4% e cargas trifásicas equilibradas; o MyGrid usado pela
co-simulação tem transformadores de 225 kVA com impedância 0,01 + 0,2j e cargas
monofásicas na fase indicada pelo campo `phase`. Se a impedância do MyGrid for pu
na base do trafo, o que não foi possível confirmar porque o pacote `mygrid` não
está no repositório, a reatância que os agentes enxergavam é cerca de cinco vezes
a do modelo com que o DSO calculava as restrições.

**Decisão sobre os transformadores.** Quando foi dada liberdade para escolher, a
potência adotada passou a ser a do `force.json`: 45, 75 e 112,5 kVA, que são
potências padronizadas de transformador de distribuição no Brasil, série da NBR
5440. Os 250 kVA do pandapower não eram dimensionamento: são os parâmetros do std
type `0.25 MVA 10/0.4 kV`, que aparece na linha comentada logo acima do
`create_transformer_from_parameters`. Com 250 kVA alimentando de 8 a 20
prosumidores de cerca de 1 kW, a restrição de carregamento de transformador do
modelo do DSO nunca atuaria. A validação foi refeita com os transformadores
novos: pior desvio 2,08e-5 pu, e a tensão mínima do caso base passou de 0,9636
para 0,9579 pu.

## 6. Fase 2: a matriz de sensibilidade

Foi escrito `grid-opentes/src/simulators/sensitivity.py`, que calcula
`S[i,j] = ∂V_i/∂P_j` por perturbação no próprio OpenDSS.

**Comparação com o Jacobiano que ela substitui.** No mesmo ponto de operação, a
sensibilidade própria média é 1,6047e-03 pu/kW pelo OpenDSS contra 1,6053e-03
pelo pandapower; o máximo é 4,2226e-03 contra 4,2242e-03. Erro relativo nos
elementos significativos: **mediana 0,04%, máximo 0,86%**. Para uma mesma
variação de ±5 kW por nó, as duas matrizes preveem ΔV que diferem em 1,9e-5 pu.

**Erro da linearização.** Com direção de perturbação fixa escalada por amplitude
e Q mantido no valor do ponto base, a razão `erro/|ΔP|²` é constante em 2,5e-5
nas quatro amplitudes testadas. Essa constância é a assinatura de que o resíduo é
puramente o termo de segunda ordem e a matriz de primeira ordem está correta.

**Custo.** 74 por 74 em 0,1 s, com 149 fluxos de potência. Os 96 pontos de
operação do dia inteiro em 9,7 s.

**Erro que custou uma rodada de depuração.** A primeira validação mostrou erro
crescendo linearmente com a amplitude, o que indicaria viés na matriz. A causa
era inconsistência entre o que a matriz mede e o que a validação fazia: S era
calculada com ΔQ = 0 e a validação deixava Q acompanhar o fator de potência.
Corrigido, o erro virou de segunda ordem limpa.

**Achado.** Repetindo a validação com o dispositivo variando Q junto com P a
fator de potência constante, o erro fica cerca de 40 vezes maior e passa a ser de
primeira ordem. Ou seja, **na restrição de tensão do DSO a hipótese ΔQ = 0 domina
o erro, não a linearização**. É propriedade da formulação da tese.

## 7. A pergunta sobre o CPLEX e o modelo estocástico

Foram feitas duas perguntas que pareciam uma só e não são.

**Sobre o CPLEX.** Foram medidos os três tipos de modelo do trabalho, em porte
real, com HiGHS e com o CPLEX local:

| Modelo | HiGHS via Pyomo | CPLEX |
|---|---|---|
| QP 74×96 (DSO e concentrador) | falha: `Highs interface does not support expressions of degree None` | ótimo em 1,66 s |
| MILP 20×96 | ótimo em 0,70 s | ótimo em 0,22 s |
| MIQP 20×96 (prosumidor) | falha | ótimo em 1,48 s |

A limitação é da interface do Pyomo com o HiGHS, não do HiGHS. A recomendação foi
ficar com o CPLEX, com o solver configurável por variável de ambiente e montado
no container por volume, nunca copiado para a imagem.

**Sobre o estocástico, houve correção de rumo.** A afirmação anterior de que a
remoção do PySP forçava o modelo determinístico estava errada. O modelo tem 9
cenários e dois estágios, e o equivalente é a forma extensiva: um único MILP com
9 cópias das variáveis de segundo estágio compartilhando as de primeiro. O PySP
serve para decompor árvores grandes por progressive hedging, e com 9 cenários não
há o que decompor. Olhando os arquivos: `ReferenceModel.py` são 204 linhas de
modelo por cenário, `generate_scenarios.py` são 348 linhas que dependem só de
numpy e pandas, e apenas `run_stochastic_model.py`, com 122 linhas, e o
`ScenarioStructure.dat` são PySP.

O custo computacional também não é obstáculo: o modelo do prosumidor roda **uma
vez** por dia simulado, no primeiro ciclo. Quem re-otimiza a cada iteração dual
são só o concentrador e o DSO.

A recomendação foi **não largar, parametrizar**: o modelo indexado por conjunto
de cenários, com 1 sendo o determinístico e 3 produzindo os 9 cenários de
preço-potência da tese. Foi a decisão adotada.

## 8. Fase 3: os modelos e a decomposição dual

Foi criado o pacote `simulators/market-opentes/` com seis módulos:
`data_prep`, `config`, `scenarios`, `optimization`, `dual` e as figuras. Ele roda
o mecanismo de forma **centralizada**, sem PADE e sem Mosaik, de propósito: para
separar o risco numérico do risco de comunicação.

**Resultado.** A carga base do SimBench não viola nada, com tensão de 0,978 a
1,028 pu. Quem cria o conflito é a programação econômica dos prosumidores, que
concentra carga e descarga nos mesmos horários de preço: aparecem 44 pontos acima
de 1,03 pu. O DSO elimina a violação já na primeira rodada, e as rodadas
seguintes negociam quem paga o ajuste.

| Caso | Violações propostas | Rodadas | λ final |
|---|---:|---:|---:|
| 1 cenário (determinístico), α 0,6 | 44 acima de 1,03 pu | 17 | 0,865 |
| 9 cenários (estocástico), α 0,6 | 35 acima de 1,03 pu | 13 | 0,285 |

O prosumidor que decide sob incerteza programa de forma menos agressiva, estressa
menos a rede, e o preço sombra necessário para resolver o conflito cai a um
terço. Isso é o que se perderia ao largar o modelo estocástico.

**O achado que explica as 8 rodadas da tese.** O `alpha = 0.0005` do código
original não converge no porte real. A diferença é de unidade: o resíduo que
alimenta a Equação 6.30 vem das mensagens ACL, onde as potências trafegam
multiplicadas por 1e3, ou seja em W, enquanto as variáveis dentro dos modelos
estão em kW. O passo efetivo da tese equivale a **α = 0,5 com resíduo em kW**.

**Varredura do passo do subgradiente:**

| α | Rodadas | Resíduo final | Comportamento |
|---:|---:|---:|---|
| 0,25 | 37 | 0,0035 kW | decai, razão 0,875 |
| 0,50 | 20 | 0,0018 kW | decai, razão 0,75 |
| **0,60** | **17** | **0,0016 kW** | decai, razão 0,70 |
| 0,65 | >40 | 0,0091 kW | decai e estaciona acima da tolerância |
| 0,75 | >40 | 2,14 kW | ciclo limite |
| 1,00 | >40 | 3,66 kW | ciclo limite maior |
| 2,00 e 4,00 | >40 | 4,00 kW | satura em 2× o limite de potência |

O que muda ao cruzar o limiar não é convergência contra divergência: é o **raio
do ciclo limite**. Em α = 2 e 4 o resíduo satura em exatamente 4,00 kW, que é o
dobro do `max_energy_flow` de 2 kW: concentrador e DSO travam em limites opostos.
Isso é o comportamento de manual do subgradiente com passo fixo, que converge
para uma vizinhança do ótimo cujo raio é proporcional ao passo.

**Passo decrescente.** Com α₀ = 2,0 e regra α/ω chega-se ao mesmo resíduo em 8
rodadas em vez de 17, e some o precipício de estabilidade. Com a ressalva de que
o critério `|Δλ| ≤ ε` passa a poder disparar pela queda do passo e não pela do
resíduo.

**Duas mudanças conscientes em relação ao original.** A direção da restrição de
balanço do prosumidor, que o `ReferenceModel.py` decidia chamando `value()` sobre
uma expressão contendo variáveis de decisão (zero na construção, o que na prática
já era a demanda sem armazenamento), passou a ser decidida pelo parâmetro de
demanda líquida. E a restrição de carregamento passou a ser por transformador,
que é a formulação da Equação 6.13, incluindo a carga base na soma.

**Completude da fase.** Numa auditoria posterior faltavam três coisas, todas
fechadas: a geração e redução de cenários por distância de Kantorovich (portada
de `generate_scenarios.py`), o `pyproject.toml` do pacote, e a figura de
convergência prometida no plano.

## 9. Fase 4: os agentes PADE

Foi escrito `pade-opentes/agents/market_agents.py`, com 33 agentes num único
processo: 1 mercado, 1 solver, 1 DSO, 5 concentradores e 25 prosumidores. Um
único `MosaikCon` vive no agente de mercado, e o passo do Mosaik fica aberto até
a rodada de negociação fechar. Mais o cenário `mosaik-opentes/scenarios/market.py`
e os serviços `pade-market` e `mosaik-market` no compose.

**Pré-requisito resolvido.** O `api_opendss.py` passou a aceitar `P_kw` e
`Q_kvar` como entrada no modelo `Load`, com P e Q independentes de propósito,
pelo mesmo motivo da Fase 2. No caminho apareceu um bug pré-existente: o
`get_data` de `Load` fazia `p_kw / 1000.0` assumindo escalar, e `get_power`
devolve tupla por fase em carga trifásica; o IEEE 13 nunca exercitou esse caso
porque as cargas dele são monofásicas. Validado por regressão contra os números
da Fase 1, agora passando pelo caminho do Mosaik.

**Três defeitos encontrados na integração:**

1. **Sem AMS rodando, o `Agent._send` do PADE descarta mensagens em silêncio.**
   Ele só entrega ao destinatário que estiver em `agentInstance.table`, e quem
   popula essa tabela é o AMS, o processo que o `pade start-runtime` sobe. Sem
   ele a tabela fica vazia, os CFP saem e nada volta. O aviso só aparece com
   `debug=True`. Como o conjunto de agentes é fixo e conhecido no arranque, a
   tabela passou a ser semeada direto em `start_market_loop`, o que dispensa o
   AMS e evita que o tráfego de registro dele polua a medição da Fase 5.

2. **`handle_all_proposes` é reentrante.** O ciclo 1 terminava várias vezes e o
   agente de mercado abria rodadas concorrentes sobre o mesmo λ, corrompendo o
   resíduo. Resolvido com guardas de estado e com a recusa de fechar rodada
   incompleta.

3. **Payloads casados por posição.** Cada concentrador cuida de um subconjunto
   dos nós, e o λ chegava como lista global casada por índice, então cada
   concentrador recebia o preço sombra de outro prosumidor. Convergia mesmo
   assim, mas a 0,863 por rodada em vez de 0,70. Só foi detectado porque a Fase 3
   centralizada servia de referência numérica. Tudo passou a ser indexado por nó.

Também se descobriu que o `ACLMessage` do PADE 3.0 não tem `set_message_length`,
que existia na 2.2 para a integração com o ns-3. O tamanho passou a ser anotado
em `message.message_length` por um helper.

**Resultado.** A negociação distribuída reproduz exatamente a centralizada: 17
rodadas, resíduo final 0,0016 kW, trajetória idêntica rodada a rodada. E o
cenário completo, com fluxo de potência não linear no OpenDSS:

| Caso | Faixa de tensão | Violações |
|---|---|---|
| Linha de base (sem negociação) | 0,97128 a **1,03487** pu | **40** acima de 1,03 |
| Negociado | 0,97128 a **1,02995** pu | **0** |

A negociação decide com o modelo linearizado e o OpenDSS confirma no fluxo não
linear, com 5e-5 pu de folga contra o limite.

**Sobre o ambiente.** O Pyomo entrou na imagem `opentes/pade:local`. O CPLEX não:
entra por volume de `${CPLEX_HOME}` para `/opt/cplex:ro`. Registrado no README do
`market-opentes` com a tabela do que funciona sem ele, o link da IBM Academic
Initiative, o aviso de que `pip install cplex` não serve porque a Community
Edition trava em 1000 variáveis, e as alternativas livres com os tempos medidos.

**Um erro de processo.** Uma execução foi lançada com `docker compose up` sem
`-d`, canalizada para `grep | head -25`, sob `timeout`. O `timeout` matou o
cliente do Compose mas não os containers, que ficaram rodando; e o `head` esperava
linhas que não vinham. A partir daí tudo passou a ser executado desanexado, com
espera por condição.

## 10. Fase 5: a camada de comunicação

Foi escrito `pade-opentes/agents/network_link.py`, sucessor do `pade.simul` do
ns-3: substitui o `_send` do agente em tempo de execução, sem tocar no núcleo do
PADE, que é compartilhado com os cenários `star`, `ieee13` e `integrated`. Três
backends: `ideal`, `lossy` (o mesmo modelo fenomenológico do `NetworkNode.cc`, em
Python) e `omnet`, que levanta `NotImplementedError` explicando o que falta.
Telemetria por mensagem em CSV.

**Dois defeitos que só existem com atraso:**

1. **O `FipaContractNetProtocol` do PADE supõe entrega imediata.** Os contadores
   internos e o conjunto efetivamente agregado deixam de coincidir quando as
   respostas chegam intercaladas: o ciclo 1 fechava com 19 das 25 programações
   **sem nenhuma perda de pacote**. Os agentes passaram a fazer contabilidade
   própria, por remetente e por número de rodada, e respostas de rodadas
   anteriores são descartadas.

2. **O FIPA não define retransmissão.** Uma rodada tem cerca de 24 mensagens, e a
   chance de perder ao menos uma a 5% é de 71%. Os ciclos 1 e 4 ganharam timeout
   com reenvio apenas aos que faltam, mais uma política explícita para quem nunca
   responde: entra com programação nula, o que é decisão de mercado e não detalhe
   de implementação, porque o prosumidor silencioso perde a chance de ser
   remunerado pelo ajuste e a rede perde o recurso dele.

**Medido:**

| Perda | Retransmissão | Convergiu | Rodadas | Retransmissões | Tempo |
|---:|---|---|---:|---:|---:|
| 0% | não se aplica | sim | 17 | 0 | 94 s |
| 5% | desligada | **não** | 1 | 0 | 23 s |
| 2% | 3 tentativas | sim | **17** | 7 | 211 s |
| 5% | 3 tentativas | chegou à rodada 16 de 17, interrompido pelo watchdog do teste | | | 420 s |
| 10% | 3 tentativas | **não** | 3 | 16 | 205 s |

Com retransmissão, a perda custa tempo e não correção: mesmas 17 rodadas, mesmo
preço sombra final. Sem ela, a negociação morre na primeira rodada. O atraso
medido a 2% foi de 6,0 s em média e 17,9 s no máximo por mensagem, dominado pela
transmissão do vetor de preço sombra, que tem 25 séries de 96 valores.

## 11. Fase 6: a fase de operação

Escopo reaberto a pedido. Foi escrito `market_opentes/operation.py`, com os dois
níveis de interferência da subseção 6.1.4.3: primeiro o DSO tenta corrigir só com
o armazenamento de rede, e se não bastar o agente de mercado abre o leilão de
operação com decomposição dual sobre um único período. Os modelos foram
parametrizados por número de períodos para poderem rodar com `periods=1`.

A realização vem de um dia diferente do reservatório de cenários, o mesmo
mecanismo que alimenta o modelo estocástico do prosumidor, então o desvio é
realista e reprodutível.

**Resultado, dia inteiro, 96 intervalos:**

| Intervalo | Desvio | V máx antes | Nível | Rodadas | V máx depois |
|---:|---:|---:|---|---:|---:|
| 36 a 40, 42, 47 | −1 a −9 kW | 1,0300 a 1,0357 | armazenamento de rede | 0 | 1,0300 |
| 41 | −12,9 kW | 1,0354 | leilão de operação | 30 | 1,0300 |
| 43 | −13,8 kW | 1,0344 | leilão de operação | 30 | 1,0300 |

Nove intervalos exigiram intervenção e nove foram resolvidos. A estrutura de dois
níveis da tese aparece sozinha nos dados: desvios pequenos o DSO absorve com o
armazenamento que ele mesmo despacha, e os dois maiores obrigam a abrir o leilão.
Nesses dois o laço dual de período único bateu no teto de 30 rodadas sem
satisfazer `|Δλ| ≤ ε`, embora a solução do DSO já fosse viável.

**Erro que custou uma rodada de depuração.** Na primeira versão o otimizador do
DSO enxergava a tensão da previsão, concluía que não havia violação e devolvia a
programação intacta enquanto o desvio real já tinha estourado o limite. O desvio
não é variável de decisão, é deslocamento do ponto de operação, e por isso entra
no V0, não nas restrições.

## 12. Fase 7: as figuras

Quatro figuras: convergência, tensão com e sem negociação, fase de operação e
custo da comunicação. A skill de visualização foi carregada; o validador de
paleta não pôde ser executado por não haver `node` no ambiente, então foi usada a
paleta de referência da própria skill em ordem fixa de slot, que ela documenta
como já aprovada.

Uma correção foi feita a partir das regras: a cor de uma série estava sendo usada
para marcar o nível de intervenção na figura de operação, o que faria a leitura
por cor apontar duas coisas diferentes. Os níveis passaram a se distinguir pela
forma, em tinta neutra.

## 13. Revisão final

**Regressão dos cenários existentes.** Os três cenários anteriores continuam
funcionando: `star`, `ieee13` e `integrated`, todos com saída zero. O `ieee13`
reproduz exatamente os valores de referência do TSRE: P_dc 3024,6 kW, P_ac 2854,2
kW e P_meas 1902,7 kW, que são os máximos do maior painel, não a soma agregada.

**Divergência encontrada no `integrated`.** O `baseline` reproduz exatamente o
documentado (Bus 652 mínima 0,9205 pu), mas o caso Volt/Var dá 0,9221 contra
0,9382 documentado, com reativo total de 454,6 kvar contra 320 kvar documentados.
Duas execuções deram o mesmo resultado, então não é a variabilidade de ordem de
mensagens que a documentação menciona. Para separar responsabilidade, o
`api_opendss.py` foi revertido ao estado anterior ao commit e o cenário rodou de
novo: **resultado idêntico, 0,9221 pu**. A divergência é anterior a este trabalho
e está entre o código da branch e o texto do `README.md` e do
`docs/INTEGRACAO.md`.

**Código morto removido**, apontado por `pyflakes`: importações não usadas em
`dual.py`, `plot_results.py`, `market_agents.py` e `network_link.py`, uma f-string
sem placeholder no gerador, e a função `_slice` não usada em `operation.py`. Após
a limpeza, a regressão do pacote foi refeita: 17 rodadas, resíduo 0,0016 kW.

**Documentação.** Foi criado `docs/MERCADO.md`, prometido na Fase 0 e nunca
escrito, com a formulação, a correspondência equação a equação com o código, os
dez desvios em relação à implementação original e as limitações conhecidas. O
`docs/ALTERACOES_INTEGRACAO.txt` ganhou a seção 10. O docstring do
`gen_market_grid.py` estava desatualizado quanto à decisão dos transformadores e
foi corrigido, junto com a referência a um documento que não existia.

## 14. Inventário do que foi criado e alterado

### Criados

| Caminho | Conteúdo |
|---|---|
| `simulators/market-opentes/pyproject.toml` | metadados e dependências do pacote |
| `simulators/market-opentes/README.md` | uso, solver, resultados medidos |
| `simulators/market-opentes/market_opentes/config.py` | monta o caso: nós, concentradores, dispositivos |
| `simulators/market-opentes/market_opentes/data_prep.py` | recorta perfis do SimBench e preços do Nordpool, mais o reservatório de cenários |
| `simulators/market-opentes/market_opentes/scenarios.py` | amostragem e redução por distância de Kantorovich |
| `simulators/market-opentes/market_opentes/optimization.py` | modelos do prosumidor, concentrador e DSO |
| `simulators/market-opentes/market_opentes/dual.py` | decomposição dual da fase de programação |
| `simulators/market-opentes/market_opentes/operation.py` | fase de operação, dois níveis |
| `simulators/market-opentes/market_opentes/plot_convergence.py` | figura de convergência |
| `simulators/market-opentes/market_opentes/plot_results.py` | figuras de tensão, operação e comunicação |
| `simulators/market-opentes/data/*.csv` | perfis de entrada e alocação de dispositivos |
| `simulators/grid-opentes/src/simulators/gen_market_grid.py` | conversor `force.json` para OpenDSS |
| `simulators/grid-opentes/src/simulators/sensitivity.py` | matriz dV/dP por perturbação |
| `simulators/grid-opentes/src/data/MVLV75/` | circuito gerado e o `force.json` de origem |
| `simulators/pade-opentes/agents/market_agents.py` | os quatro agentes FIPA e o solver |
| `simulators/pade-opentes/agents/network_link.py` | camada de rede |
| `simulators/mosaik-opentes/scenarios/market.py` | cenário da co-simulação |
| `docs/MERCADO.md` | formulação, correspondência e desvios |
| `docs/DIARIO_MERCADO_2026-08.md` | este documento |

### Alterados

| Caminho | Alteração |
|---|---|
| `simulators/grid-opentes/src/simulators/api_opendss.py` | modelo `Load` aceita `P_kw`/`Q_kvar` como entrada; `get_data` de `Load` corrigido para carga trifásica |
| `simulators/pade-opentes/Dockerfile` | numpy, pandas e pyomo na imagem; CPLEX por volume |
| `docker-compose.yaml` | serviços `pade-market` e `mosaik-market`, profile `market` |
| `README.md` | cenário `market` na tabela, com o aviso sobre o solver |
| `docs/ALTERACOES_INTEGRACAO.txt` | seção 10, com o changelog da camada de mercado |
| `.gitignore` | produtos da camada de mercado |

## 15. Achados, por ordem de importância

1. **O modelo de rede da tese tem duas versões incompatíveis** (pandapower e
   MyGrid), com transformadores, impedâncias e modelo de carga diferentes.
   Unificar em OpenDSS resolve.
2. **O `alpha = 5e-4` do código original está em unidade diferente das variáveis
   dos modelos**: resíduo em W contra variáveis em kW. O passo efetivo é 0,5.
3. **O tamanho das mensagens no modelo de rede da tese é arbitrário.** O código
   original chama `set_message_length(np.random.randint(1000, 1500))` para as
   propostas e `set_message_length(100)` para os CFP (`market_agent.py`, linhas
   66, 79, 256 e 269), enquanto o conteúdo real de um CFP de rodada, medido, é de
   **35.663 bytes** em JSON. A análise de comunicação
   da tese subestima o tráfego em mais de uma ordem de grandeza. A implementação
   nova usa o tamanho serializado real.
4. **O `FipaContractNetProtocol` do PADE supõe entrega imediata** e perde
   propostas quando há atraso, mesmo sem perda de pacotes.
5. **O FIPA não define retransmissão**, e sem ela a negociação não sobrevive a
   nenhuma perda realista.
6. **Sem AMS, o PADE descarta mensagens em silêncio.**
7. **A hipótese ΔQ = 0 domina o erro da restrição de tensão**, cerca de 40 vezes
   o erro da linearização, se o dispositivo mantiver fator de potência constante.
8. **O passo constante do subgradiente converge a uma vizinhança**, não ao ótimo,
   e o raio cresce com α. Acima de 0,6 nesta rede o raio ultrapassa a tolerância.
9. **Não há restrição de estado de carga terminal**, nem na tese nem aqui: as
   baterias despejam energia no último intervalo, 50 kW agregados, elevando a
   tensão a 1,02 pu.
10. **O `get_data` de `Load` do `api_opendss` estava quebrado para carga
    trifásica**, sem que ninguém notasse porque o IEEE 13 só tem cargas
    monofásicas.
11. **A documentação do cenário `integrated` está desatualizada** em relação ao
    código da branch, no ganho do Volt/Var e no reativo total.

## 16. O que fica em aberto

- **Ligar o backend `omnet`**: falta um segundo ponto de entrada no
  `MosaikBridge` que aceite um lote de mensagens fora do passo do Mosaik e
  devolva atraso e descarte por mensagem. O backend `lossy` reproduz o mesmo
  modelo de canal em Python enquanto isso.
- **Montar o IEEE European LV Test Feeder** como caso principal citável. A rede
  MVLV75 é o caso de regressão.
- **Decidir sobre a restrição de SoC terminal** com o orientador, ciente de que
  ela refaz todos os números.
- **Levar a fase de operação para os agentes**, já que hoje ela roda centralizada.
- **Reproduzir o modelo 6TiSCH da tese** no OMNeT++, com PER por distância, para
  que os resultados de comunicação sejam comparáveis.
- **Reconciliar a documentação do `integrated`** com o comportamento atual do
  código.
- **Considerar trocar o critério de parada** para o resíduo primal, mantendo o
  `|Δλ|` como registro de compatibilidade.
