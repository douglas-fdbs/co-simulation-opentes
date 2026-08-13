# Insumos da apresentação

Arquivos que os geradores `../gerar_apresentacao.py` e
`../gerar_apresentacao_pptx.py` consomem.

| Arquivo | O que é |
|---|---|
| `figs.py` | codifica as figuras de `market-opentes/data/` em base64 e grava o `figs.json` |
| `figs.json` | as figuras embutidas, mais o logotipo do GREI como máscara |
| `logo_creme.png`, `logo_verde.png` | o logotipo já tingido, para o PPTX |

O HTML embute as figuras porque a página publicada não pode buscar recurso
externo. O logotipo entra no HTML como máscara CSS, que se recolore conforme o
tema; o PowerPoint não tem esse mecanismo, e por isso as duas variantes tingidas
existem.

## Regenerar

```bash
python3 apresentacao_assets/figs.py   # só quando as figuras mudarem
python3 gerar_apresentacao.py         # HTML
python3 gerar_apresentacao_pptx.py    # PPTX (precisa de python-pptx, bs4, pillow)
soffice --headless --convert-to pdf apresentacao_mercado.pptx   # PDF
```

Identidade visual do manual de marca do GREI: verde `#2F5E4B`, creme `#F4FFEB`,
tipografia Exo 2 nos títulos e Poppins no texto de apoio. As duas fontes são
nomeadas primeiro na pilha e entram automaticamente para quem as tiver
instaladas; sem elas, cai numa alternativa geométrica próxima.

## Figuras de arquitetura

`arquitetura_simsg.png` e `fluxo_cosimulacao.png` são geradas por
`market_opentes/plot_arquitetura.py`, e não desenhadas à mão, para poderem ser
refeitas quando a arquitetura mudar:

```bash
docker run --rm -v "$PWD/simulators/market-opentes:/market" -w /market \
  opentes/mosaik:local python -m market_opentes.plot_arquitetura
```

`rede_teste.png`, `agentes_kok.png` e `agentes_rede.png` vêm da tese de
referência (MELO, 2022) e são reproduzidas com citação nos slides.
