# Mercado transativo: formulação, correspondência com a tese e desvios

Documento de referência da camada de mercado (`simulators/market-opentes`
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

Critério de parada da tese: `|λ_ω − λ_ω+1| ≤ ε`. Ele é um resíduo primal
escalado pelo passo, e por isso **não é confiável sob passo decrescente**:
medido, o passo decrescente declarou convergência em 45 rodadas com resíduo
primal de 0,0222 kW, cinco vezes pior que o passo constante em 60 rodadas
(0,0041 kW). O teste disparou pela queda do passo, não pelo acordo entre as
partes. Os dois resíduos são reportados lado a lado; compare pelo primal.

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

## 5.2 Os dispositivos do prosumidor que não entram na demanda

O `config.json` aloca seis tipos de dispositivo. Apenas três chegam à rede, e
isso é uma característica da implementação de referência, não uma omissão nossa:
no `Prosumer.step` do `prosumer.py` original, as contribuições de
`freely_control_gen`, `shiftable_load` e `buffering_device` estão **comentadas**
(linhas 591, 603 e 609). Os dispositivos são instanciados, recebem `step()` e o
resultado é descartado.

| Dispositivo | Nós | Entra na demanda? |
|---|---:|---|
| `user_action_device` | 68 | sim, é a carga base |
| `stochastic_gen` | 34 | sim, é a geração PV |
| `storage_device` | 25 | sim, é a flexibilidade negociada |
| `dso_storage_device` | 23 | sim, despachado pelo DSO |
| `shiftable_load` | 68 | **não**, inerte no código original |
| `buffering_device` | 54 | **não**, inerte no código original |
| `freely_control_gen` | 3 | **não**, inerte no código original |

Implementar os três inertes afastaria o caso da tese em vez de aproximá-lo dela.
Fica registrado como extensão possível, não como pendência de fidelidade.

## 5.3 A liquidação e o preço locacional

A tese propõe dois ambientes de contratação (subseção 6.1.1): um mercado futuro
bilateral, de preço fixo, em que o prosumidor só pode comprar, e um mercado spot
de tempo real, em que pode comprar e vender. O agente de mercado grava as
transações num `transactions_data.hdf5`.

Duas observações sobre o registro original. **O preço do bilateral não é
gravado**: `save_transactions_data` é chamado sem `value_um`, então o campo fica
no default `-1.0`. E **o spot é registrado ao preço spot puro**, sem qualquer
adicional vindo da negociação.

Sobre o DLMP a tese é explícita (subseção 6.1.4.4): *"Este trabalho não entrará no
mérito da questão de como tratar os valores encontrados para λ(t,l) como valores
financeiros reais. Os valores de preços encontrados serão interpretados apenas
como uma variável de controle"*. A Figura 45 mostra λ como "preço adicional", sem
unidade monetária e sem aplicação a transação nenhuma.

### λ não está em unidade monetária

Isso não é detalhe de implementação. No ótimo do concentrador, derivando
`Ck (x − x_init)² + λ x` em relação a `x`:

```
2 Ck (x − x_init) + λ = 0    =>    λ = 2 Ck (x_init − x)
```

ou seja, **λ tem unidade de `Ck` vezes potência**. Com o `Ck = 1` adimensional da
tese, λ é numericamente um desvio de potência, não um preço. Para virar preço, o
peso da função objetivo precisa ser calibrado em moeda, `Ck` em EUR/(kW²·h), e aí

```
DLMP(t,l) = preço_spot(t) + λ(t,l) / Δt × 1000     [EUR/MWh]
```

`market_opentes/settlement.py` expõe essa calibração em `MARKET_CK_EUR`. Sem ela,
o DLMP é reportado com a conversão aplicada sobre o `Ck = 1`, e deve ser lido como
**sinal**, na mesma condição em que a tese o lê. O aviso vai no cabeçalho do CSV,
para que ninguém cite o número como preço sem saber disso.

Saídas: `transactions.csv` (energia e custo por prosumidor nos dois mercados),
`dlmp.csv` (preço por nó e por intervalo, com o adicional separado do spot) e
`flexibility.csv` (quanto cada prosumidor deslocou e a que preço), gerados por
`python -m market_opentes.dual --settle-dir data`. A figura `dlmp.png` é o
equivalente 2D da Figura 45 da tese.

### O mercado bilateral não cumpre função na formulação da tese

Medido, variando só o que a formulação permite variar:

| Configuração | Bilateral | Spot | Custo total |
|---|---:|---:|---:|
| 1 cenário, neutro ao risco | 3,1 kWh (1,5%) | 211,1 kWh | 4,24 EUR |
| 9 cenários, neutro ao risco | 2,5 kWh (1,3%) | 188,4 kWh | 4,28 EUR |
| 9 cenários + multa por desvio (20 EUR/MWh) | 2,8 kWh (1,4%) | 195,8 kWh | 4,27 EUR |
| 9 cenários + aversão ao risco (CVaR, β = 0,5) | **7,8 kWh (3,8%)** | 195,6 kWh | 4,79 EUR |

A tese apresenta os dois ambientes como uma escolha entre segurança e risco
(subseção 6.1.1: contratar no bilateral "sem maiores riscos financeiros" ou
"correr um pouco mais de risco" no spot). A formulação não realiza essa escolha:
as Equações 6.1 a 6.9 minimizam **custo esperado**, sem termo de aversão, e o
mercado de tempo real não tem limite de quantidade. Sob neutralidade ao risco, a
decisão entre um preço fixo e um preço variável é uma comparação de esperanças, e
o bilateral só entra nos intervalos em que o spot esperado passa de 38 EUR/MWh.

A multa por desvio, que o texto da tese descreve mas as equações não têm, **não
resolve**: comprar mais no bilateral reduz o nível do spot, não a dispersão dele
entre cenários, então a multa é indiferente à escolha entre os mercados. Isso foi
medido, não deduzido.

O que dá papel próprio ao contrato de preço fixo é aversão ao risco. Com um termo
de CVaR, a participação do bilateral quase triplica e o custo sobe 12%, que é o
prêmio pago pela proteção. As três extensões estão implementadas e desligadas por
padrão (`MARKET_DEVIATION_PENALTY`, `MARKET_CVAR_BETA`, `MARKET_CVAR_ALPHA`): o
default reproduz a tese.

## 6. Limitações conhecidas
- **A restrição de estado de carga terminal é NOSSA, não da tese.** A Eq. 6.9 não
  a tem, e sem ela o modelo despeja a energia da bateria no último intervalo,
  porque ela não vale nada na função objetivo. Está ligada por padrão
  (`MARKET_TERMINAL_SOC=1`); desligá-la reproduz o comportamento do original.
- **A restrição de tensão precisa de margem contra o próprio erro.** O
  otimizador cola a solução no limite, e o erro da linearização (1e-4 a 6e-4 pu)
  vira violação no fluxo de potência completo: sem margem, a negociação promete
  0,9700 pu e o OpenDSS entrega 0,96924, com 104 pontos violados. Com
  `V_BACKOFF = 1e-3` aplicado aos limites dentro do modelo, o fluxo não linear
  fica em 0,97020 pu e nenhuma violação. Isso NÃO existe na tese, que usa a mesma
  restrição linearizada sem recuo; só aparece quando a restrição passa a atuar de
  fato.
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
