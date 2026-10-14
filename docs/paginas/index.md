---
hide:
  - navigation
  - toc
---

<div class="grei-hero" markdown>
![GREI](assets/grei-logo.png){ .off-glb }

# Mercado transativo por fase sobre a IEEE 13 barras

Prosumidores com baterias negociam a programação do dia seguinte com o operador
da rede, e um preço sombra coordena os dois lados para que a tensão fique dentro
da faixa **em cada fase**. A negociação acontece entre agentes **PADE**, a rede
elétrica é resolvida pelo **OpenDSS**, as mensagens podem atravessar uma rede
6TiSCH no **OMNeT++**, e o **Mosaik** sincroniza tudo.

[Começar](instalacao.md){ .md-button .md-button--primary }
[Como funciona](arquitetura.md){ .md-button }
</div>

## A pergunta

Num alimentador com muita geração fotovoltaica, os prosumidores, cada um
otimizando o próprio custo, programam as baterias de um jeito que piora a tensão
da rede. O mecanismo da tese de Lucas S. Melo (UFC, 2022) resolve isso com uma
decomposição dual: o operador e os prosumidores trocam propostas até concordarem,
e o multiplicador de Lagrange da restrição de acordo é o **preço sombra**.

A tese aplica o mecanismo a uma rede equilibrada, com uma tensão e um preço por
barra. A IEEE 13 é desequilibrada, e nela a média das fases esconde violação.
Aqui a análise é **por fase**: o operador vigia a tensão de cada fase, e o preço
sombra é calculado por fase, o que só tem sentido com inversores que despacham
cada fase separadamente.

## O que foi medido

<div class="grei-numeros" markdown>
<div markdown>
<strong>134 → 9</strong>
<span>leituras de fase acima de 1,03 pu na co-simulação: negociando pela média das fases e negociando por fase</span>
</div>
<div markdown>
<strong>0</strong>
<span>leituras fora da ANSI Range A na co-simulação por fase, contra 3 pela média</span>
</div>
<div markdown>
<strong>−71 µpu/kW</strong>
<span>efeito na fase B de 1 kW injetado só na fase A da barra 671: o acoplamento que a média ignora</span>
</div>
<div markdown>
<strong>0,00044 pu</strong>
<span>erro médio do circuito IEEE 13 contra o perfil de tensão publicado</span>
</div>
</div>

## Por onde seguir

<div class="grei-cartoes" markdown>

<div markdown>
### :material-rocket-launch: Instalação e execução
Requisitos, os quatro comandos do `run.sh` e o que cada um grava.

[Ler mais →](instalacao.md)
</div>

<div markdown>
### :material-sitemap: A plataforma
Os cinco contêineres, o que acontece numa execução e o mapa das pastas.

[Ler mais →](arquitetura.md)
</div>

<div markdown>
### :material-transmission-tower: O caso IEEE 13
Como o alimentador foi adotado: cargas, PV, portas por fase, armazenamento e
regulador.

[Ler mais →](caso.md)
</div>

<div markdown>
### :material-swap-horizontal: O modelo de mercado
A formulação, a análise por fase, os inversores de quatro e de três fios e os
desvios em relação à tese.

[Ler mais →](mercado.md)
</div>

<div markdown>
### :material-chart-line: Resultados
Por barra contra por fase, na negociação e na co-simulação, com as figuras.

[Ler mais →](resultados.md)
</div>

</div>

## Quem fez

Trabalho do time **TTESO** no projeto OpenTES, do [GREI](https://github.com/grei-ufc),
o Grupo de Redes Elétricas Inteligentes da Universidade Federal do Ceará, sobre
componentes desenvolvidos pelas equipes do projeto:

| Equipe | Contribuição | Onde está |
|---|---|---|
| TSCC | rede de comunicação e a ponte com o Mosaik | `simulators/comm-opentes`, `mosaik-opentes` |
| TSRE | rede elétrica, sistemas fotovoltaicos e o simulador OpenDSS | `simulators/grid-opentes` |
| TTESO | agentes, otimização, mercado transativo e a integração | `simulators/pade-opentes`, `market-opentes` |
