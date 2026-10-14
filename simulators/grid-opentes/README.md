# grid-opentes: a rede elétrica

O OpenDSS, chamado pelo `py-dss-interface`, com o caso IEEE 13 barras do mercado.
Roda como contêiner `grid`; o Mosaik se conecta a ele (`./run.sh market`, na raiz).

```
src/simulators/
  opendss_simulator.py   entrada do contêiner (--remote :5671)
  api_opendss.py         o circuito exposto ao Mosaik: cargas, barras, reguladores
  opendss_wrapper.py     o OpenDSS por trás da API
  sensitivity.py         matrizes de sensibilidade de tensão, por barra e por fase
  gen_ieee13_market.py   monta o caso de mercado (./run.sh caso)
  pv_creator.py          curvas de irradiância e temperatura dos PV
  pv_validator.py        conferências das curvas e da ligação dos PV
src/data/
  13Bus/                 o caso: circuito, perfis, alocação, matrizes
  InfoPV/                dados de estação solar que alimentam o pv_creator
```

O simulador aceita **uma única** conexão Mosaik e encerra depois dela: não sonde
a porta com TCP. Veja `docs/paginas/caso.md` e `docs/paginas/arquitetura.md`.
