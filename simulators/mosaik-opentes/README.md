# mosaik-opentes: o orquestrador

O Mosaik sincroniza os simuladores no mesmo relógio, em passos de 15 minutos.

```
scenarios/market.py         o cenário: liga os agentes PADE ao circuito do OpenDSS
collectors/elec_collector.py grava tensões e potências de cada passo (result_<tag>.csv)
```

O cenário cria uma entidade para cada barra com prosumidor, cada porta de
armazenamento por fase e cada regulador de tensão, e liga as tensões de todas as
barras ao coletor. A mesma imagem roda o coletor (contêiner `collector`) e as
figuras do mercado (`./run.sh figuras`).
