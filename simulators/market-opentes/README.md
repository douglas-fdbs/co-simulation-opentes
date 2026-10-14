# market-opentes: o modelo de mercado

Biblioteca Python com a formulação do mercado transativo: os modelos de
otimização em Pyomo, a decomposição dual, a fase de operação, a liquidação e as
figuras. Não é contêiner: os agentes em `simulators/pade-opentes` a importam, e
ela também roda sozinha no `./run.sh centralizado`.

```
market_opentes/
  config.py         o caso, as variáveis de armazenamento (por barra ou por porta) e as chaves
  optimization.py   prosumidor (Eq. 6.1-6.9), concentrador (6.25-6.26), DSO (6.27-6.29)
  dual.py           a decomposição dual centralizada (Eq. 6.30)
  operation.py      a fase de operação, intervalo a intervalo
  scenarios.py      geração e redução de cenários do prosumidor (Kantorovich)
  settlement.py     transações, preço locacional e flexibilidade
  figuras_tese.py   as figuras, no formato da tese
  plot_msgs.py      as figuras do traço de mensagens
```

O solver padrão é o IBM CPLEX, montado do host (`CPLEX_HOME`): o modelo do
prosumidor é inteiro-misto e os do concentrador e do DSO são quadráticos. A
formulação completa está em `docs/paginas/mercado.md`.
