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
| 6.1.5 | Rede LPWA 6TiSCH | `comm-opentes/Tisch.cc` | Reproduz os 10 a 90 s da tese sem ajuste |
| 6.2.2 | Fase de programação da operação | Fluxo completo | 442 para 4 pontos violados no fluxo não linear |
| 6.2.3 | Fase de operação, dois níveis | `MarketAgent.start_operation` | 22 intervalos tratados, todos resolvidos |

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

**O que fazer:** implementar o mecanismo de ±10% como opção
(`MARKET_REALIZED=perturb`), mantendo o dia alternativo como o caso severo. Custo
baixo, e é o que torna os resultados de operação comparáveis.

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

### 3.3 Os três ciclos não respeitam os minutos 1, 5 e 10

A tese posiciona os três ciclos de troca de mensagens em instantes definidos
dentro da janela de 15 minutos: AC com seus AP no minuto 1, AD com os AC no
minuto 5, AM com AC e AD no minuto 10. Aqui os ciclos rodam em sequência, com
`call_later` de 0,05 a 0,1 s entre eles.

Enquanto a entrega é instantânea isso não muda resultado. Com a rede 6TiSCH no
laço passa a mudar, porque o orçamento de tempo de cada ciclo é justamente o que
determina se ele fecha dentro da janela. É a condição para reproduzir a Figura 58
da tese.

### 3.4 Limite térmico de condutor

O AD da tese previne "ultrapassagem do limite térmico dos condutores e
transformadores". Aqui só o carregamento por transformador está implementado
(Eq. 6.13), e isso está registrado como desvio consciente número 5, porque é a
restrição da formulação e é a que tem limite conhecido. Fica anotado que a
descrição textual do agente é mais ampla que a formulação.

### 3.5 Saídas de resultado que a tese tem e nós não

- Tabelas 18 e 19 do Apêndice A: tensão máxima e mínima por nó, com horário de
  ocorrência.
- Figuras 51 e 52: programação de demanda por nó ao longo das iterações de
  negociação, comparando o que o AD e o AC adotam.
- Figura 58: linha do tempo das mensagens por ciclo.

Nenhuma delas é difícil; são consultas sobre dados que já existem.

## 4. Fora do escopo por decisão da própria tese

HVAC e veículos elétricos: a subseção 6.1.3 os exclui explicitamente, por não
haver modelo de otimização que integre a dinâmica deles. Não são lacuna.

## 5. Pendências que já eram conhecidas

- Montar o IEEE European LV Test Feeder como caso principal citável; a MVLV75 é o
  caso de regressão.
- Reconciliar a documentação do cenário `integrated` com o comportamento atual.
- Decidir sobre a restrição de estado de carga terminal com o orientador.
- Rodar o `./run.sh market` completo sobre a rede 6TiSCH, e não só o teste
  isolado de negociação.
