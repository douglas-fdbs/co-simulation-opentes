# Mercado transativo: formulação, correspondência com a tese e desvios

Documento de referência da camada de mercado (`simulators_teams/market-opentes`
e `pade-opentes/agents/market_agents.py`). Ele existe para responder três
perguntas sem que ninguém precise ler o código: **qual é o modelo matemático,
onde ele está implementado, e no que a nossa implementação difere da original.**

Fonte: MELO, Lucas Silveira. *Modelo de simulação computacional multidomínio
para análise de redes elétricas inteligentes com aplicação em transações
econômicas de energia*. Tese de doutorado, UFC, 2022. Capítulo 6.
Implementação de referência: repositório `market-simulation` (GREI-UFC).

---

## 1. Os quatro papéis

| Sigla | Papel | Quantidade | Onde está |
|---|---|---:|---|
| AP | Agente Prosumidor | 25 (os nós com armazenamento) | `market_agents.ProsumerAgent` |
| AC | Agente Concentrador | 5 (um por transformador) | `market_agents.ConcentratorAgent` |
| AD | Agente DSO | 1 | `market_agents.DSOAgent` |
| AM | Agente Mercado | 1 | `market_agents.MarketAgent` |
| — | Solver | 1 | `market_agents.SolverAgent` |

O AP programa os seus recursos e responde aos leilões. O AC agrega os
prosumidores de um transformador e despacha o armazenamento de rede sob ele. O
AD detém o modelo da rede e as restrições operacionais. O AM coordena a
descoberta do preço sombra. O solver existe para que os modelos Pyomo rodem fora
do reactor do Twisted, e é o mesmo papel do `solver_agent.py` original.

## 2. Modelos de otimização

### 2.1 Agente Prosumidor (Eq. 6.1 a 6.9)

Minimiza o custo operacional esperado, decidindo em dois estágios: no primeiro,
quanto contratar no mercado bilateral e como programar o armazenamento; no
segundo, os lances no mercado de tempo real, por cenário.

```
min  Σ_t Φ_bl · APP_bl(t) · Δt  +  Σ_z Σ_t π(z) · Φ_tr(z,t) · APP_tr(z,t) · Δt
```

Sujeito ao balanço energético (6.3), à impossibilidade de venda da energia
comprada no bilateral (6.4 e 6.5) e à operação do armazenamento (6.6 a 6.9):
exclusão entre carga e descarga por variáveis binárias, limites de potência e
memória do estado de carga.

Implementação: `market_opentes/optimization.py::solve_prosumer`.

### 2.2 Agente Concentrador (Eq. 6.25 e 6.26)

```
min  Σ_t Σ_l C_k · (ACP_init(t,l) − ACP_result(t,l))²  +  Σ_t Σ_l λ_ω(t,l) · ACP_result(t,l)
sujeito a   Σ_t ACP_result(t,l) · Δt  ≥  D_l · Σ_t ACP_init(t,l) · Δt
```

Implementação: `market_opentes/optimization.py::solve_concentrator`.

### 2.3 Agente DSO (Eq. 6.27 a 6.29)

```
min  Σ_t Σ_l [ a · (ADP_init − ADP_result)² + b · (ADP̄_init − ADP̄_result)² ]
     −  Σ_t Σ_l λ_ω(t,l) · ADP_result(t,l)
sujeito a   Σ_l (ADP_result + ADP̄_result)  ≤  ADP_trans_max(t)
            U_min  ≤  U_0(t,l) + ΔU(t,l)  ≤  U_max
```

Implementação: `market_opentes/optimization.py::solve_dso`.

**O sinal de λ é assimétrico de propósito**: positivo no concentrador (6.25),
negativo no DSO (6.27). Isso é da formulação, não erro de implementação, e o
código original faz o mesmo.

### 2.4 Sensibilidade de tensão (Eq. 6.15 a 6.17)

A restrição de tensão é linearizada em torno do ponto de operação, considerando
apenas potência ativa (ΔQ = 0):

```
ΔU(t,l) = J⁻¹₂₁ · ( ADP_result + ADP̄_result )
```

O trabalho original obtinha `J⁻¹₂₁` do pandapower, porque o MyGrid resolve o
fluxo por varredura direta-inversa e não produz Jacobiano. **Aqui a mesma
grandeza é obtida por perturbação no próprio OpenDSS**, o que elimina o segundo
simulador: `grid-opentes/src/simulators/sensitivity.py`.

Validação: a matriz numérica bate com `J⁻¹₂₁` do pandapower com erro relativo
mediano de 0,04% e máximo de 0,86%; a previsão de ΔV para uma mesma variação
difere em 1,9e-5 pu.

### 2.5 Decomposição dual (Eq. 6.24 e 6.30)

A restrição de acoplamento `ACP_result = ADP_result` é relaxada por multiplicador
de Lagrange, e o AM atualiza o preço sombra por subgradiente:

```
λ_ω+1(t,l) = λ_ω(t,l) + α_ω · ( ACP_result(t,l) − ADP_result(t,l) )
```

Critério de parada da tese: `|λ_ω − λ_ω+1| ≤ ε`.

Implementação: `market_opentes/dual.py` (centralizada) e
`market_agents.MarketAgent` (distribuída, sobre FIPA).

## 3. Desvios em relação à implementação original

Cada item aqui é uma decisão consciente, não uma omissão.

| # | Original | Aqui | Motivo |
|---|---|---|---|
| 1 | PySP para o modelo estocástico | Forma extensiva em Pyomo | PySP foi removido do Pyomo 6. Com 9 cenários não há o que decompor: a forma extensiva é um único MIQP. O número de cenários virou parâmetro (1 = determinístico). |
| 2 | `J⁻¹₂₁` do pandapower | `∂V/∂P` por perturbação no OpenDSS | Elimina o segundo simulador de rede e vale para rede desbalanceada. |
| 3 | pandapower e MyGrid, dois modelos da mesma rede | Um modelo em OpenDSS | Ver seção 4. |
| 4 | Trafos de 250 kVA uniformes | 45/75/112,5 kVA do `force.json` | Os 250 kVA eram resíduo do std type `0.25 MVA 10/0.4 kV`. Com eles a restrição de carregamento nunca atua. |
| 5 | Restrição de corrente em todos os ramos por matriz de incidência | Carregamento por transformador | É a formulação da Eq. 6.13 e é a que tem limite conhecido. |
| 6 | Conteúdo das mensagens em `pickle` + `literal_eval` | JSON | O `pickle` sobre ACL é frágil, e o tamanho serializado alimenta o modelo de rede. |
| 7 | Um simulador Mosaik por agente (75 sockets) | Um simulador para todos | Escala e reduz o número de containers. |
| 8 | Sem retransmissão | Timeout com reenvio aos faltantes | Ver seção 5. |
| 9 | Direção da restrição de balanço decidida por `value()` sobre variáveis | Decidida pelo parâmetro de demanda líquida | O original lia o valor inicial de uma variável de decisão (zero na construção), o que na prática já era a demanda sem armazenamento. Agora é explícito. |
| 10 | Fase de operação com leilão em tempo real | Implementada em `operation.py`, fora do escopo principal | Escopo do TCC travado na fase de programação. |

## 4. A divergência entre os dois modelos de rede do trabalho original

O `market-simulation` descreve a mesma rede de duas formas incompatíveis:

| | pandapower (usado pelo AD) | MyGrid (usado pela co-simulação) |
|---|---|---|
| Transformador | 250 kVA, vk = 4%, vkr = 1,2% | 225 kVA, impedância 0,01 + 0,2j |
| Cargas | trifásicas equilibradas | monofásicas, na fase do campo `phase` |
| Linhas | std types do pandapower | modelo de condutor (Carson) |

Se a impedância do MyGrid for pu na base do trafo, o que não foi possível
confirmar porque o pacote `mygrid` não está no repositório, a reatância que os
agentes enxergavam é cerca de cinco vezes a do modelo com que o DSO calculava as
restrições. Unificar em OpenDSS resolve isso, e é uma das contribuições do
trabalho.

## 5. O que a camada de comunicação revelou

Dois problemas que só aparecem quando a entrega deixa de ser instantânea:

1. **O `FipaContractNetProtocol` do PADE supõe entrega imediata.** Os contadores
   internos (`received_qty` contra `cfp_qty`) e o conjunto efetivamente agregado
   divergem com atraso: o ciclo 1 fechava com 19 das 25 programações **sem
   nenhuma perda de pacote**. Os agentes passaram a fazer contabilidade própria,
   por remetente e por número de rodada.

2. **O FIPA não define retransmissão.** Uma rodada tem cerca de 24 mensagens, e a
   probabilidade de perder ao menos uma a 5% é de 71%. Os ciclos 1 e 4 ganharam
   timeout com reenvio apenas aos faltantes, e uma política explícita para quem
   nunca responde: entra com programação nula, isto é, perde a remuneração pelo
   ajuste e a rede perde o recurso dele.

## 5.1 O tamanho das mensagens no modelo de rede original

O `market-simulation` informa ao simulador de rede um tamanho de mensagem
**arbitrário**: `set_message_length(100)` para os CFP e
`set_message_length(np.random.randint(1000, 1500))` para as propostas
(`market_agent.py`, linhas 66, 79, 256 e 269). O conteúdo real de um CFP de
rodada, com o vetor de preço sombra de 25 nós por 96 intervalos mais as
programações, é de **35.663 bytes** em JSON.

Consequência: a análise de comunicação da tese, que reporta mensagens de 100 a
1500 bytes e entrega entre 10 e 90 s numa rede LPWA de 50 kbps, subestima o
tráfego em mais de uma ordem de grandeza. A implementação nova usa o tamanho
serializado real (`_set_content` anota `message.message_length`), então os tempos
de entrega medidos aqui e os da tese **não são diretamente comparáveis**.

## 6. Limitações conhecidas

- **Não há restrição de estado de carga terminal.** Nem na Eq. 6.9 da tese nem
  aqui. Como a energia que sobra na bateria no fim do dia não vale nada na função
  objetivo, o modelo a despeja: no intervalo 95 o armazenamento agregado
  descarrega 50 kW e a tensão sobe a 1,02 pu. A correção é uma restrição
  `SoC(95) ≥ SoC(0)`, e refaz todos os números.
- **A hipótese ΔQ = 0 domina o erro da restrição de tensão.** Se o dispositivo
  mantiver fator de potência constante em vez de reativo nulo, o erro é cerca de
  40 vezes o da própria linearização.
- **O critério `|Δλ| ≤ ε` é um resíduo primal escalado por α.** Com passo
  decrescente ele pode disparar pela queda do passo e não pela do resíduo.
  Compare sempre pelo resíduo primal, que é reportado ao lado.
- **O passo constante não converge ao ótimo**, e sim a uma vizinhança cujo raio
  cresce com α. Acima de α = 0,6 nesta rede o raio ultrapassa a tolerância.
- **O backend `omnet` da camada de rede ainda não está ligado**: falta um segundo
  ponto de entrada no `MosaikBridge`. O backend `lossy` reproduz o mesmo modelo
  de canal do `NetworkNode.cc` em Python.
- **A rede é o caso de regressão, não o caso principal.** O `force.json` é um
  grafo sintético do trabalho original. O IEEE European LV Test Feeder, decidido
  como caso principal citável, ainda não foi montado.
