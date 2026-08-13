"""Monta a apresentação do mercado transativo como um arquivo HTML único.

As figuras entram embutidas em base64 porque a página publicada não pode buscar
recurso externo. O conteúdo vem dos documentos do repositório.
"""
import json
import pathlib

SP = pathlib.Path(__file__).resolve().parent / "apresentacao_assets"
FIGS = json.loads((SP / "figs.json").read_text())

CSS = """
/* Identidade GREI: verde #2F5E4B e creme #F4FFEB, do manual de marca.
   Tipografia da marca: Exo 2 (títulos) e Poppins (apoio). A página publicada não
   pode buscar fonte externa, então as duas são nomeadas primeiro na pilha e
   entram para quem as tiver instaladas; a alternativa é tonalmente próxima. */
:root {
  --green:     #2F5E4B;
  --green-2:   #24483A;
  --green-lt:  #4C8168;
  --cream:     #F4FFEB;

  --paper:     #FBFEF6;
  --surface:   #ffffff;
  --ink:       #16241D;
  --ink-2:     #35473E;
  --slate:     #64786C;
  --line:      #DDE7DA;

  --accent:    #2F5E4B;
  --accent-dim:#E4F0E5;
  --warm:      #B65A2B;
  --warm-dim:  #F8EAE0;
  --good:      #2F7D57;
  --good-dim:  #E0F1E6;

  --shadow: 0 1px 2px rgba(22,36,29,.05), 0 10px 28px rgba(22,36,29,.07);

  --title: "Exo 2", "Exo2", ui-sans-serif, system-ui, "Segoe UI", Roboto, sans-serif;
  --body:  "Poppins", ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto,
           "Helvetica Neue", Arial, sans-serif;
  --mono:  ui-monospace, "SF Mono", "JetBrains Mono", "Cascadia Mono", Menlo,
           Consolas, monospace;
}

@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --paper:     #17302688;
    --paper:     #142B21;
    --surface:   #1C382C;
    --ink:       #F4FFEB;
    --ink-2:     #D3E6CE;
    --slate:     #93AE9C;
    --line:      #2C5343;
    --accent:    #8FD9AE;
    --accent-dim:#1E3F31;
    --warm:      #E89A6B;
    --warm-dim:  #3A2418;
    --good:      #6FCB99;
    --good-dim:  #16352A;
    --shadow: 0 1px 2px rgba(0,0,0,.35), 0 10px 28px rgba(0,0,0,.3);
  }
}
:root[data-theme="dark"] {
  --paper:     #142B21;
  --surface:   #1C382C;
  --ink:       #F4FFEB;
  --ink-2:     #D3E6CE;
  --slate:     #93AE9C;
  --line:      #2C5343;
  --accent:    #8FD9AE;
  --accent-dim:#1E3F31;
  --warm:      #E89A6B;
  --warm-dim:  #3A2418;
  --good:      #6FCB99;
  --good-dim:  #16352A;
  --shadow: 0 1px 2px rgba(0,0,0,.35), 0 10px 28px rgba(0,0,0,.3);
}

* { box-sizing: border-box; }

body {
  margin: 0;
  background: var(--paper);
  color: var(--ink);
  font-family: var(--body);
  font-size: 17px;
  line-height: 1.55;
  -webkit-font-smoothing: antialiased;
}

.deck { scroll-snap-type: y mandatory; overflow-y: auto; height: 100vh; }

.slide {
  scroll-snap-align: start;
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  justify-content: center;
  padding: clamp(2rem, 5vh, 4rem) clamp(1.5rem, 6vw, 6rem) clamp(4.5rem, 8vh, 6rem);
  position: relative;
  border-bottom: 1px solid var(--line);
}
.slide > .inner { width: 100%; max-width: 1180px; margin: 0 auto; }

/* A capa usa o verde da marca como fundo, que é como o manual apresenta o logo. */
.slide.cover { background: var(--green); border-bottom: 0; }
.slide.cover, .slide.cover .lead, .slide.cover p { color: var(--cream); }
.slide.cover h1 { color: var(--cream); }
.slide.cover .eyebrow { color: color-mix(in srgb, var(--cream) 82%, transparent); }
.slide.cover .eyebrow .dot { border-color: color-mix(in srgb, var(--cream) 70%, transparent); }
.slide.cover .eyebrow::after { background: color-mix(in srgb, var(--cream) 30%, transparent); }
.slide.cover .stat .n { color: var(--cream); }
.slide.cover .stat .l { color: color-mix(in srgb, var(--cream) 72%, transparent); }
.slide.cover .footer-note { color: color-mix(in srgb, var(--cream) 60%, transparent); }

/* ---- logotipo ---------------------------------------------------------- */
.logo {
  display: block;
  background-color: currentColor;
  -webkit-mask-repeat: no-repeat; mask-repeat: no-repeat;
  -webkit-mask-size: contain;    mask-size: contain;
  -webkit-mask-position: left center; mask-position: left center;
}
.logo.big  { width: clamp(180px, 22vw, 300px); aspect-ratio: RATIO; margin-bottom: 2.2rem; }
.logo.mini { width: 66px; aspect-ratio: RATIO; opacity: .38; }
.slide-mark { position: absolute; right: clamp(1.5rem, 6vw, 6rem); bottom: 2.9rem; color: var(--slate); }

/* ---- tipografia -------------------------------------------------------- */
.eyebrow {
  font-family: var(--mono);
  font-size: .72rem;
  letter-spacing: .16em;
  text-transform: uppercase;
  color: var(--accent);
  margin: 0 0 1.1rem;
  display: flex; align-items: center; gap: .7rem;
}
/* O traço terminado em círculo cita o terminal do logotipo. */
.eyebrow::after {
  content: ""; flex: 1; height: 1px; background: var(--line); max-width: 110px;
  position: relative;
}
.eyebrow .dot {
  width: 7px; height: 7px; border-radius: 50%;
  border: 1.5px solid var(--accent); flex: none; margin-left: -.35rem;
}
h1 {
  font-family: var(--title);
  font-size: clamp(2.1rem, 5.2vw, 3.9rem);
  line-height: 1.05; letter-spacing: -.02em; font-weight: 700;
  margin: 0 0 1.2rem; text-wrap: balance;
}
h2 {
  font-family: var(--title);
  font-size: clamp(1.55rem, 3.3vw, 2.5rem);
  line-height: 1.14; letter-spacing: -.015em; font-weight: 700;
  margin: 0 0 1.4rem; text-wrap: balance;
}
h3 { font-family: var(--title); font-size: 1.02rem; font-weight: 700; margin: 0 0 .45rem; }
p { margin: 0 0 1rem; max-width: 68ch; color: var(--ink-2); }
p.lead { font-size: 1.2rem; line-height: 1.5; color: var(--ink); max-width: 60ch; }
strong { color: var(--ink); font-weight: 600; }
.muted { color: var(--slate); }
.small { font-size: .88rem; }
code { font-family: var(--mono); font-size: .88em; }

/* ---- grades ------------------------------------------------------------ */
.cols  { display: grid; gap: 1.5rem; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); }
.cols-2{ display: grid; gap: 1.8rem; grid-template-columns: 1fr 1fr; align-items: start; }
.cols-3{ display: grid; gap: 1.2rem; grid-template-columns: repeat(3, 1fr); }
@media (max-width: 980px) { .cols-2, .cols-3 { grid-template-columns: 1fr; } }

/* Um item de grade tem `min-width: auto`, que resolve para o conteudo minimo.
   Com grade dentro de grade, a trilha 1fr interna encolhia ate a MAIOR PALAVRA e
   o texto saia uma palavra por linha. Zerar o minimo desfaz isso. */
.cols > *, .cols-2 > *, .cols-3 > *, .ba > *, .arch-row > * { min-width: 0; }

.card {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 10px;
  padding: 1.1rem 1.2rem;
  box-shadow: var(--shadow);
}
.card .tag {
  font-family: var(--mono); font-size: .68rem; letter-spacing: .12em;
  text-transform: uppercase; color: var(--slate); display: block; margin-bottom: .4rem;
}

/* ---- números ----------------------------------------------------------- */
.stat { display: flex; flex-direction: column; gap: .25rem; }
.stat .n {
  font-family: var(--title);
  font-size: clamp(1.9rem, 4.4vw, 3.2rem);
  font-weight: 700; letter-spacing: -.025em; line-height: 1;
  font-variant-numeric: tabular-nums; color: var(--ink);
}
.stat .l { font-size: .82rem; color: var(--slate); line-height: 1.4; }
.n.blue { color: var(--accent); } .n.green { color: var(--good); } .n.amber { color: var(--warm); }

.hero-number { display: flex; align-items: baseline; gap: 1.4rem; flex-wrap: wrap; margin: .5rem 0 1.6rem; }
.hero-number .big {
  font-family: var(--title); font-weight: 700; letter-spacing: -.035em;
  font-size: clamp(3.2rem, 10vw, 7.5rem); line-height: .9;
  font-variant-numeric: tabular-nums;
}
.arrow { color: var(--slate); font-size: clamp(1.6rem, 4vw, 2.6rem); }

/* ---- antes/depois ------------------------------------------------------ */
.ba { display: grid; grid-template-columns: 1fr auto 1fr; gap: 1.4rem; align-items: stretch; }
@media (max-width: 820px) { .ba { grid-template-columns: 1fr; } .ba .sep { display: none; } }
.ba .sep { width: 1px; background: var(--line); }
.panel { border-radius: 10px; padding: 1.2rem 1.3rem; border: 1px solid var(--line); }
.panel.before { background: var(--warm-dim); border-color: color-mix(in srgb, var(--warm) 30%, var(--line)); }
.panel.after  { background: var(--good-dim); border-color: color-mix(in srgb, var(--good) 30%, var(--line)); }
.panel h3 { display: flex; align-items: center; gap: .5rem; }
.panel .pill {
  font-family: var(--mono); font-size: .62rem; letter-spacing: .12em; text-transform: uppercase;
  padding: .18rem .48rem; border-radius: 4px; color: #fff;
}
.panel.before .pill { background: var(--warm); }
.panel.after  .pill { background: var(--good); }
:root[data-theme="dark"] .panel .pill,
:root:not([data-theme="light"]) .panel .pill { color: #10241B; }

/* ---- listas ------------------------------------------------------------ */
/* O marcador e posicionado em absoluto, e NAO como item de grade.
   Com `display: grid` na <li>, um <strong> vira item de grade e o texto que vem
   DEPOIS dele vira um item anonimo separado, que cai na linha seguinte, dentro da
   coluna estreita do marcador. O resultado e o texto saindo uma palavra por
   linha. Em fluxo normal com recuo, o conteudo permanece inline e isso nao
   acontece, independentemente de quantos elementos houver dentro da <li>. */
ul.clean { list-style: none; padding: 0; margin: 0; display: grid; gap: .6rem; }
ul.clean li {
  position: relative; padding-left: 1.35rem; color: var(--ink-2);
}
ul.clean li::before {
  content: ""; position: absolute; left: 0; top: .52rem;
  width: 7px; height: 7px; border-radius: 50%;
  border: 1.5px solid var(--accent); box-sizing: border-box;
}
ul.steps { list-style: none; padding: 0; margin: 0; display: grid; gap: .95rem; counter-reset: s; }
ul.steps li {
  position: relative; padding-left: 2.75rem; min-height: 1.75rem;
  counter-increment: s; color: var(--ink-2);
}
ul.steps li::before {
  content: counter(s);
  position: absolute; left: 0; top: .05rem;
  font-family: var(--mono); font-size: .78rem; font-weight: 600;
  width: 1.75rem; height: 1.75rem; border-radius: 50%;
  display: grid; place-items: center;
  background: var(--accent-dim); color: var(--accent);
}

/* ---- tabelas ----------------------------------------------------------- */
.tw { overflow-x: auto; }
table { border-collapse: collapse; width: 100%; font-size: .93rem; }
th, td { text-align: left; padding: .55rem .7rem; border-bottom: 1px solid var(--line); color: var(--ink-2); }
th {
  font-family: var(--mono); font-size: .69rem; letter-spacing: .1em;
  text-transform: uppercase; color: var(--slate); font-weight: 500;
}
td.num, th.num { text-align: right; font-family: var(--mono); font-variant-numeric: tabular-nums; }
tr.hi td { background: var(--accent-dim); }
td .ok  { color: var(--good); font-weight: 600; }
td .bad { color: var(--warm); font-weight: 600; }

/* ---- figuras ----------------------------------------------------------- */
figure { margin: 0; }
figure img {
  width: 100%; height: auto; display: block; border-radius: 8px;
  border: 1px solid var(--line); background: #fff;
}
figcaption { font-size: .85rem; color: var(--slate); margin-top: .6rem; max-width: 78ch; }
.fig-slide .inner { max-width: 1240px; }

/* ---- diagrama ---------------------------------------------------------- */
.arch { display: grid; gap: .8rem; }
.arch-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: .8rem; }
@media (max-width: 820px) { .arch-row { grid-template-columns: 1fr 1fr; } }
.node {
  border: 1px solid var(--line); border-radius: 8px; padding: .8rem .9rem;
  background: var(--surface); text-align: center;
}
.node .nm { font-family: var(--title); font-weight: 700; font-size: .98rem; color: var(--ink); }
.node .rl { font-size: .78rem; color: var(--slate); margin-top: .15rem; }
.node.hub { background: var(--green); border-color: var(--green); }
.node.hub .nm, .node.hub .rl { color: var(--cream); }
.node.hub .rl { opacity: .82; }

/* ---- navegação --------------------------------------------------------- */
.rail { position: fixed; left: 0; right: 0; bottom: 0; height: 3px; background: var(--line); z-index: 20; }
.rail .fill { height: 100%; width: 0; background: var(--green); transition: width .18s ease; }
:root[data-theme="dark"] .rail .fill,
:root:not([data-theme="light"]) .rail .fill { background: var(--accent); }
.counter {
  position: fixed; right: clamp(1rem, 3vw, 2rem); bottom: 1.1rem; z-index: 21;
  font-family: var(--mono); font-size: .74rem; color: var(--slate);
  background: color-mix(in srgb, var(--paper) 88%, transparent);
  padding: .25rem .55rem; border-radius: 5px; border: 1px solid var(--line);
  font-variant-numeric: tabular-nums;
}
.hint {
  position: fixed; left: clamp(1rem, 3vw, 2rem); bottom: 1.15rem; z-index: 21;
  font-family: var(--mono); font-size: .72rem; color: var(--slate); transition: opacity .4s ease;
}
.footer-note {
  position: absolute; left: clamp(1.5rem, 6vw, 6rem); bottom: 1.5rem;
  font-family: var(--mono); font-size: .7rem; color: var(--slate);
}

:focus-visible { outline: 2px solid var(--accent); outline-offset: 3px; }
@media (prefers-reduced-motion: reduce) { * { transition: none !important; scroll-behavior: auto !important; } }

@media print {
  .rail, .counter, .hint { display: none; }
  .deck { height: auto; overflow: visible; }
  .slide { min-height: auto; page-break-after: always; border: 0; }
}
"""


def fig(name, caption, extra=""):
    return (f'<figure{extra}><img src="{FIGS[name]}" alt="{caption}">'
            f'<figcaption>{caption}</figcaption></figure>')


SLIDES = []


def slide(html, cls=""):
    # Marca discreta no rodape de cada slide, menos na capa, que ja traz o logo
    # grande. A area de protecao do manual e respeitada pelo padding do slide.
    marca = "" if "cover" in cls else '<span class="logo mini slide-mark" aria-hidden="true"></span>'
    SLIDES.append(f'<section class="slide {cls}"><div class="inner">{html}</div>{marca}</section>')


# ---------------------------------------------------------------------------
# 1. Capa
# ---------------------------------------------------------------------------
slide("""
<span class="logo big" role="img" aria-label="GREI, Grupo de Redes Eletricas Inteligentes"></span>
<p class="eyebrow"><span class="dot"></span>OpenTES &middot; Time TTESO</p>
<h1>O mercado transativo entrando na rede</h1>
<p class="lead">Como a plataforma de co-simulação passou de um teste de controle
em 13 barras para uma negociação entre 33 agentes numa rede de 75 barras, e o que
isso mudou na tensão, no preço e no tráfego de mensagens.</p>
<div class="cols" style="margin-top:2.2rem;max-width:820px">
  <div class="stat"><span class="n green">337 &rarr; 0</span>
    <span class="l">pontos de subtensão eliminados no fluxo de potência não linear</span></div>
  <div class="stat"><span class="n blue">34</span>
    <span class="l">rodadas de negociação até o acordo entre concentradores e DSO</span></div>
  <div class="stat"><span class="n">75</span>
    <span class="l">barras, contra as 13 do cenário anterior</span></div>
</div>
""", "cover")

# ---------------------------------------------------------------------------
# 2. O problema
# ---------------------------------------------------------------------------
slide("""
<p class="eyebrow"><span class="dot"></span>O problema</p>
<h2>Quem decide na rede de distribuição deixou de ser só a distribuidora</h2>
<div class="cols-2">
  <div>
    <p>Com geração solar e armazenamento atrás do medidor, o consumidor vira
    <strong>prosumidor</strong>: produz, armazena e negocia energia. Cada um
    otimizando o próprio bolso, ao mesmo tempo.</p>
    <p>O resultado agregado dessas decisões individuais pode violar a rede que
    todos compartilham. Baterias carregando juntas de madrugada afundam a tensão;
    solar injetando junto ao meio-dia levanta demais.</p>
    <p class="muted small">Um <strong>sistema transativo de energia</strong> resolve isso
    por preço, e não por comando: a rede sinaliza onde dói, e quem pode ceder
    flexibilidade é remunerado por cedê-la.</p>
  </div>
  <div class="card">
    <span class="tag">a pergunta que a plataforma responde</span>
    <p style="margin:0"><strong>A negociação entre agentes, com as mensagens
    passando por uma rede de comunicação real, consegue manter a tensão dentro
    do limite sem mandar ninguém fazer nada?</strong></p>
  </div>
</div>
""")

# ---------------------------------------------------------------------------
# 3. Três domínios
# ---------------------------------------------------------------------------
slide("""
<p class="eyebrow"><span class="dot"></span>Por que co-simulação</p>
<h2>Três domínios que normalmente se simulam separados</h2>
<div class="cols-3">
  <div class="card"><span class="tag">domínio elétrico</span>
    <h3>Onde a tensão cai</h3>
    <p class="small" style="margin:0">Fluxo de potência não linear, limites de
    tensão e carregamento de transformador.</p></div>
  <div class="card"><span class="tag">domínio de comunicação</span>
    <h3>Se a mensagem chega</h3>
    <p class="small" style="margin:0">Atraso, perda de pacote e roteamento
    multi-salto entre os agentes.</p></div>
  <div class="card"><span class="tag">domínio de decisão</span>
    <h3>Quem propõe o quê</h3>
    <p class="small" style="margin:0">Otimização de cada agente e o protocolo de
    negociação entre eles.</p></div>
</div>
<p style="margin-top:1.6rem">Simular só o primeiro dá um estudo de fluxo de
potência. Simular os três juntos mostra o que nenhum deles mostra sozinho: por
exemplo, que um protocolo de negociação que funciona com entrega instantânea
<strong>perde propostas quando a entrega atrasa</strong>, e a programação
resultante viola justamente a tensão que deveria proteger.</p>
""")


# ---------------------------------------------------------------------------
# Bloco teórico, baseado na defesa de doutorado (Melo, 2022)
# ---------------------------------------------------------------------------
slide("""
<p class="eyebrow"><span class="dot"></span>Fundamento &middot; definição</p>
<h2>Sistema de energia transativo</h2>
<div class="card" style="border-left:4px solid var(--accent);max-width:74ch">
  <p class="lead" style="margin:0">Sistema de mecanismos econômicos e de controle
  que permite o <strong>equilíbrio dinâmico entre geração e demanda</strong> ao
  longo de toda a infraestrutura da rede elétrica, utilizando
  <strong>valor econômico como parâmetro operacional</strong>.</p>
</div>
<p class="small muted" style="margin-top:.9rem">Definição adotada na tese de
referência, a partir de Abrishambaf et al. (2019).</p>
<div class="cols-3" style="margin-top:1.8rem">
  <div class="card"><span class="tag">o que o move</span>
    <h3>Preço, não comando</h3>
    <p class="small" style="margin:0">O sinal que coordena não é uma ordem de
    despacho, é um valor. Quem pode ceder flexibilidade responde a ele.</p></div>
  <div class="card"><span class="tag">onde ele age</span>
    <h3>Toda a infraestrutura</h3>
    <p class="small" style="margin:0">Da unidade consumidora à subestação, e não
    apenas no atacado.</p></div>
  <div class="card"><span class="tag">o que ele equilibra</span>
    <h3>Geração e demanda, em tempo real</h3>
    <p class="small" style="margin:0">O equilíbrio é dinâmico: reavaliado a cada
    intervalo de 15 minutos.</p></div>
</div>
""")

slide("""
<p class="eyebrow"><span class="dot"></span>Fundamento &middot; por que co-simulação</p>
<h2>Quatro naturezas diferentes no mesmo problema</h2>
<div class="cols" style="margin-bottom:1.6rem">
  <div class="card"><span class="tag">contínuo</span><h3>Processos físicos</h3>
    <p class="small" style="margin:0">O fluxo de potência na rede elétrica.</p></div>
  <div class="card"><span class="tag">discreto</span><h3>Tecnologia da informação</h3>
    <p class="small" style="margin:0">Mensagens, atrasos e perdas na rede de
    comunicação.</p></div>
  <div class="card"><span class="tag">estocástico</span><h3>Processos incertos</h3>
    <p class="small" style="margin:0">Clima, irradiância e comportamento do
    usuário.</p></div>
  <div class="card"><span class="tag">decisão</span><h3>Comportamentos</h3>
    <p class="small" style="margin:0">Controle e negociação, por sistemas
    multiagentes.</p></div>
</div>
<p>Nenhuma ferramenta única trata bem as quatro. A co-simulação mantém cada
domínio no simulador que o representa melhor e <strong>sincroniza o tempo</strong>
entre eles, em vez de forçar tudo num modelo só.</p>
<p class="small muted">É a mesma justificativa da tese de referência, que trata a
co-simulação como um meta-modelo de simulação e adota o Mosaik como
co-simulador.</p>
""")

slide("""
<p class="eyebrow"><span class="dot"></span>Fundamento &middot; agentes</p>
<h2>Por que sistemas multiagentes</h2>
<div class="cols-2">
  <div>
    <p>Um agente é uma entidade de software com três características que
    interessam aqui:</p>
    <ul class="clean" style="margin-top:.9rem">
      <li><strong>Autonomia</strong> &mdash; decide sozinho, a partir do próprio
      objetivo, sem receber ordem de um controlador central</li>
      <li><strong>Proatividade</strong> &mdash; toma iniciativa, não apenas
      responde a estímulo</li>
      <li><strong>Sociabilidade</strong> &mdash; conversa com outros agentes por
      um protocolo padronizado</li>
    </ul>
    <p class="small muted" style="margin-top:1rem">São exatamente os requisitos de
    um mercado: participantes com interesses próprios que precisam chegar a um
    acordo sem uma autoridade que arbitre.</p>
  </div>
  <div class="card">
    <span class="tag">a plataforma</span>
    <h3>PADE</h3>
    <p class="small">Python Agent DEvelopment framework, desenvolvido no próprio
    grupo. Implementa os padrões da <strong>FIPA</strong>: linguagem de
    comunicação, protocolos de interação e ambiente de execução.</p>
    <p class="small" style="margin:0"><strong>O que mudou nesta etapa:</strong> a
    tese usava PADE 2.2 com Python 3.6 e um módulo de integração com o ns-3 que
    <strong>não existe mais</strong> na versão 3.0. A modernização para Python
    3.12 e a reconstrução dessa camada são entrega deste projeto.</p>
  </div>
</div>
""")

slide("""
<p class="eyebrow"><span class="dot"></span>Fundamento &middot; o modelo de mercado</p>
<h2>Dois ambientes de contratação, mais um de validação</h2>
<ul class="steps" style="max-width:80ch">
  <li><strong>Mercado futuro bilateral, de tarifa fixa.</strong> O prosumidor
  contrata com antecedência a um preço combinado. Só pode comprar, nunca
  revender.</li>
  <li><strong>Mercado spot de tempo real.</strong> Preço informado 15 minutos
  antes da entrega. Aqui o prosumidor pode comprar e vender, e é onde a incerteza
  entra na decisão dele.</li>
  <li><strong>Ambiente de validação, o mercado de restrições.</strong> A
  distribuidora verifica se o conjunto das propostas cabe na rede. Quando não
  cabe, a precificação é alterada até caber. É onde nasce o preço locacional.</li>
</ul>
<div class="card" style="margin-top:1.6rem;max-width:80ch">
  <span class="tag">a ideia central</span>
  <p style="margin:0">A rede não proíbe: ela <strong>encarece</strong>. Quem
  insistir em consumir onde a rede aperta paga mais; quem ceder é remunerado. O
  despacho sai do bolso de cada um, e não de uma ordem.</p>
</div>
""")

slide("""
<p class="eyebrow"><span class="dot"></span>Fundamento &middot; a arquitetura de referência</p>
<h2>De um modelo geral para uma aplicação transativa</h2>
<div class="ba">
  <div class="panel" style="background:var(--surface)">
    <h3>SiMSG</h3>
    <p class="small" style="margin:.4rem 0 0">Um modelo de simulação para redes
    elétricas inteligentes em geral. Define quais blocos existem, o que cada um
    representa e como se relacionam. Combina três ingredientes: co-simulação,
    sistemas multiagentes e uma metodologia de implementação por reaproveitamento
    de modelos.</p>
  </div>
  <div class="sep"></div>
  <div class="panel" style="background:var(--accent-dim);border-color:var(--accent)">
    <h3>SiMTES</h3>
    <p class="small" style="margin:.4rem 0 0">Uma instância do SiMSG aplicada a
    sistemas transativos. Acrescenta os quatro papéis de agente, os modelos de
    otimização de cada um e o mecanismo de descoberta de preço.</p>
  </div>
</div>
<p style="margin-top:1.5rem"><strong>É o SiMTES que este trabalho implementa</strong>,
sobre a mesma rede e com o mesmo comportamento de mercado. O que muda são as
ferramentas de cada camada, e cada troca tem motivo.</p>
""")

slide("""
<p class="eyebrow"><span class="dot"></span>Fundamento &middot; o que trocamos</p>
<h2>Mesma arquitetura, ferramentas diferentes</h2>
<div class="tw">
<table>
  <thead><tr><th>Camada</th><th>Tese, 2022</th><th>Aqui</th><th>Motivo da troca</th></tr></thead>
  <tbody>
    <tr><td>Agentes</td><td>PADE 2.2, Python 3.6</td><td>PADE 3.0, Python 3.12</td><td>A versão antiga não roda em Python moderno</td></tr>
    <tr><td>Comunicação</td><td>ns-3</td><td>OMNeT++</td><td>O módulo de integração com o ns-3 foi removido do PADE 3.0</td></tr>
    <tr><td>Rede elétrica</td><td>pandapower e MyGrid</td><td>OpenDSS</td><td>Os dois modelos da mesma rede divergiam entre si</td></tr>
    <tr><td>Otimização</td><td>CPLEX com PySP</td><td>CPLEX com Pyomo</td><td>O PySP foi removido do Pyomo 6</td></tr>
  </tbody>
</table>
</div>
""")

# ---------------------------------------------------------------------------
# 4 e 5. Antes e depois
# ---------------------------------------------------------------------------
slide("""
<p class="eyebrow"><span class="dot"></span>O salto</p>
<h2>De um teste de controle para um mercado</h2>
<div class="ba">
  <div class="panel before">
    <h3><span class="pill">antes</span> IEEE 13 barras</h3>
    <ul class="clean small" style="margin-top:.8rem">
      <li>13 barras, 5 inversores fotovoltaicos</li>
      <li>Controle <strong>Volt/Var</strong>: cada inversor reage localmente à
      própria tensão</li>
      <li>Agentes trocam medição e comando, sem negociar nada</li>
      <li>Sem modelo econômico, sem preço</li>
      <li>Resultado: desvio-padrão da tensão &minus;10%, a barra crítica 652 indo
      de 0,920 para 0,938 pu</li>
    </ul>
  </div>
  <div class="sep"></div>
  <div class="panel after">
    <h3><span class="pill">agora</span> MVLV75 com mercado</h3>
    <ul class="clean small" style="margin-top:.8rem">
      <li>75 barras, 7 em média e 68 em baixa tensão, 5 transformadores</li>
      <li><strong>33 agentes</strong> negociando: 25 prosumidores, 5
      concentradores, DSO e mercado</li>
      <li>Cada agente resolve o próprio problema de otimização</li>
      <li>Preço sombra descoberto por iteração, não imposto</li>
      <li>Resultado: <strong>337 pontos de subtensão vão a zero</strong>, mínima
      de 0,93946 para 0,97033 pu</li>
    </ul>
  </div>
</div>
<p class="small muted" style="margin-top:1.2rem">A diferença não é só de porte. No
Volt/Var o inversor obedece a uma curva; aqui o prosumidor <strong>propõe</strong>,
o DSO <strong>contesta</strong> quando a rede não aguenta, e o preço é o que
concilia os dois.</p>
""")

# ---------------------------------------------------------------------------
# 6. Fundamento: TES
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# 7. Os agentes
# ---------------------------------------------------------------------------
slide("""
<p class="eyebrow"><span class="dot"></span>Arquitetura de agentes</p>
<h2>Quatro papéis, 33 agentes num processo</h2>
<div class="cols">
  <div class="card"><span class="tag">AP &middot; 25 agentes</span>
    <h3>Prosumidor</h3>
    <p class="small" style="margin:0">Faz o papel de um gerenciador de energia
    residencial. Programa a própria bateria e decide quanto comprar no mercado
    bilateral e no spot, sob incerteza.</p></div>
  <div class="card"><span class="tag">AC &middot; 5 agentes</span>
    <h3>Concentrador</h3>
    <p class="small" style="margin:0">Um por transformador. Agrega as propostas
    dos prosumidores sob ele e despacha o armazenamento de rede que o DSO
    determina.</p></div>
  <div class="card"><span class="tag">AD &middot; 1 agente</span>
    <h3>DSO</h3>
    <p class="small" style="margin:0">Detém o modelo da rede. Verifica tensão e
    carregamento, e recusa programações que violem a operação.</p></div>
  <div class="card"><span class="tag">AM &middot; 1 agente</span>
    <h3>Mercado</h3>
    <p class="small" style="margin:0">Coordena a descoberta de preço. Abre as
    rodadas, coleta as propostas e atualiza &lambda; até haver acordo.</p></div>
</div>
<p class="small muted" style="margin-top:1.4rem">Sobre <strong>PADE 3.0</strong>,
com protocolos FIPA padronizados: ContractNet para os leilões, Subscribe para o
despacho. Mais um agente de solução, que roda os modelos de otimização fora do
laço de eventos.</p>
""")

# ---------------------------------------------------------------------------
# 8. Referências
# ---------------------------------------------------------------------------
slide("""
<p class="eyebrow"><span class="dot"></span>Base de referência</p>
<h2>De onde vem cada peça</h2>
<div class="tw">
<table>
  <thead><tr><th>Fonte</th><th>O que tiramos dela</th></tr></thead>
  <tbody>
    <tr><td><strong>MELO, L. S.</strong> Tese de doutorado, UFC, 2022 &mdash;
        capítulo 6 e apêndices A&ndash;C</td>
        <td>Formulação completa do mercado, a rede de 75 barras, os parâmetros dos
        dispositivos, as coordenadas dos agentes e a matriz de adjacência da rede
        de comunicação</td></tr>
    <tr><td><strong>MELO et al.</strong> <em>Co-simulation platform for the
        assessment of transactive energy systems</em>, EPSR 223, 2023</td>
        <td>Confirmação dos resultados e da arquitetura; não publica os
        parâmetros do algoritmo</td></tr>
    <tr><td><strong>MELO et al.</strong> Integração PADE/Mosaik, 2020</td>
        <td>O padrão de integração por API de baixo nível, que usamos</td></tr>
    <tr><td><strong>KOK, K.</strong> 2013</td>
        <td>A hierarquia de agentes prosumidor, concentrador, DSO e mercado</td></tr>
    <tr><td><strong>LE et al.</strong> 2009 &middot; <strong>MUNICIO et al.</strong> 2019
        &middot; <strong>PRANDO et al.</strong> 2019</td>
        <td>Modelo de propagação Pister-Hack, o simulador 6TiSCH e a conversão de
        RSSI para taxa de erro de pacote</td></tr>
    <tr><td><strong>SimBench</strong> &middot; <strong>Nordpool</strong></td>
        <td>Curvas de carga e geração, e a série de preço spot</td></tr>
    <tr><td><strong>Repositório <code>market-simulation</code></strong> (GREI-UFC)</td>
        <td>Implementação de referência da tese, usada para conferir cada decisão</td></tr>
  </tbody>
</table>
</div>
""")

# ---------------------------------------------------------------------------
# 9. Arquitetura de co-simulação
# ---------------------------------------------------------------------------
slide("""
<p class="eyebrow"><span class="dot"></span>A plataforma</p>
<h2>Quatro simuladores, um maestro</h2>
<div class="arch">
  <div class="arch-row">
    <div class="node"><div class="nm">PADE 3.0</div><div class="rl">agentes e negociação</div></div>
    <div class="node"><div class="nm">OMNeT++</div><div class="rl">rede de comunicação</div></div>
    <div class="node"><div class="nm">OpenDSS</div><div class="rl">fluxo de potência</div></div>
    <div class="node"><div class="nm">Pyomo + CPLEX</div><div class="rl">otimização</div></div>
  </div>
  <div class="arch-row" style="grid-template-columns:1fr">
    <div class="node hub"><div class="nm">Mosaik 3.5</div>
      <div class="rl">orquestra o tempo e transporta os dados entre eles</div></div>
  </div>
</div>
<div class="cols-2" style="margin-top:1.6rem">
  <div>
    <h3>O que o Mosaik faz</h3>
    <p class="small">Decide quem executa em cada instante e leva o resultado de um
    simulador à entrada do outro. Nenhum simulador conhece os demais.</p>
  </div>
  <div>
    <h3>Como roda</h3>
    <p class="small">Um contêiner Docker por simulador, com um comando único:
    <code>./run.sh market</code>. A execução é reprodutível e isolada.</p>
  </div>
</div>
""")

# ---------------------------------------------------------------------------
# 10. A rede
# ---------------------------------------------------------------------------
slide("""
<p class="eyebrow"><span class="dot"></span>O caso de estudo</p>
<h2>A rede MVLV75</h2>
<div class="cols" style="margin-bottom:1.6rem">
  <div class="stat"><span class="n">75</span><span class="l">barras: 7 em 13,8 kV e 68 em 380 V</span></div>
  <div class="stat"><span class="n">5</span><span class="l">transformadores de 45, 75 e 112,5 kVA</span></div>
  <div class="stat"><span class="n">34</span><span class="l">barras com geração solar, 50% das de baixa tensão</span></div>
  <div class="stat"><span class="n">25</span><span class="l">barras com armazenamento de prosumidor</span></div>
  <div class="stat"><span class="n">23</span><span class="l">barras com armazenamento de rede, despachado pelo DSO</span></div>
</div>
<div class="cols-2">
  <div class="card"><span class="tag">como ela chegou aqui</span>
    <p class="small" style="margin:0">O grafo da tese foi convertido para um
    circuito OpenDSS completo. A validação comparou barra a barra contra o modelo
    de referência em seis cenários de carga, incluindo um com fluxo reverso.
    <strong>Pior desvio: 2,08&times;10<sup>-5</sup> pu.</strong></p></div>
  <div class="card"><span class="tag">horizonte</span>
    <p class="small" style="margin:0">24 horas em 96 intervalos de 15 minutos.
    Limites operacionais de <strong>0,97 a 1,03 pu</strong>. A programação é
    feita no dia anterior; a operação corrige a cada 15 minutos.</p></div>
</div>
""")

# ---------------------------------------------------------------------------
# 11. Os três modelos
# ---------------------------------------------------------------------------
slide("""
<p class="eyebrow"><span class="dot"></span>O que cada agente resolve</p>
<h2>Três problemas de otimização, um por papel</h2>
<div class="cols-3">
  <div class="card"><span class="tag">prosumidor</span>
    <h3>Minimiza o custo esperado</h3>
    <p class="small">Decide em dois estágios: quanto contratar no bilateral e como
    programar a bateria; depois, os lances no spot, por cenário.</p>
    <p class="small muted" style="margin:0">Programação quadrática inteira mista,
    com binárias que impedem carregar e descarregar ao mesmo tempo.</p></div>
  <div class="card"><span class="tag">concentrador</span>
    <h3>Defende os prosumidores</h3>
    <p class="small">Minimiza o desvio da programação proposta, penalizado pelo
    preço &lambda;, com uma garantia mínima de energia entregue.</p>
    <p class="small muted" style="margin:0">Problema quadrático.</p></div>
  <div class="card"><span class="tag">DSO</span>
    <h3>Defende a rede</h3>
    <p class="small">Minimiza o desvio da programação, ponderando prosumidor e
    armazenamento de rede, sujeito a tensão e carregamento.</p>
    <p class="small muted" style="margin:0">O sinal de &lambda; entra invertido em
    relação ao concentrador: é a disputa, posta na função objetivo.</p></div>
</div>
""")

# ---------------------------------------------------------------------------
# 12. Decomposição dual
# ---------------------------------------------------------------------------
slide("""
<p class="eyebrow"><span class="dot"></span>Como eles chegam a acordo</p>
<h2>O preço não é arbitrado, é descoberto</h2>
<div class="cols-2">
  <div>
    <ul class="steps">
      <li>O concentrador propõe uma programação <strong>x</strong> que serve aos
      prosumidores dele.</li>
      <li>O DSO responde com a programação <strong>y</strong> que a rede
      aguenta.</li>
      <li>O agente de mercado mede a discordância e ajusta o preço:
      <code>&lambda; &larr; &lambda; + &alpha;(x &minus; y)</code>.</li>
      <li>Com o preço novo, os dois recalculam. Repete até
      <strong>x &asymp; y</strong>.</li>
    </ul>
    <p class="small muted" style="margin-top:1.1rem">Onde a rede não aperta, a
    discordância é zero desde a primeira rodada e o preço fica em zero. O preço
    aparece <strong>só onde e quando há conflito</strong>.</p>
  </div>
  <div class="card">
    <span class="tag">um detalhe que vale a atenção</span>
    <p class="small" style="margin:0 0 .8rem">&lambda; é o multiplicador de Lagrange
    da restrição de acoplamento. Ele é <strong>propriedade do problema</strong>,
    não do algoritmo: dois métodos convergentes chegam ao mesmo &lambda;, em
    número diferente de rodadas.</p>
    <p class="small" style="margin:0">Isso virou ferramenta de diagnóstico. Quando
    o nosso &lambda; não batia com o da tese, a conclusão não era "o algoritmo
    está errado", e sim "os problemas são diferentes" &mdash; e deu para medir
    exatamente em quê.</p>
  </div>
</div>
""")

# ---------------------------------------------------------------------------
# 13. Restrição de tensão + contribuição
# ---------------------------------------------------------------------------
slide("""
<p class="eyebrow"><span class="dot"></span>A restrição que amarra tudo</p>
<h2>Como o DSO sabe que a tensão vai violar</h2>
<div class="cols-2">
  <div>
    <p>A tensão é linearizada em torno do ponto de operação por uma matriz de
    sensibilidade: quanto cada quilowatt injetado em cada nó move a tensão de
    todos os outros.</p>
    <p class="small muted">O trabalho original extraía essa matriz do jacobiano de
    um <strong>segundo simulador de rede</strong>, o que obrigava a manter dois
    modelos da mesma rede &mdash; que, no repositório de referência, divergiam
    entre si em transformador e em modelo de carga.</p>
  </div>
  <div class="card">
    <span class="tag">contribuição deste trabalho</span>
    <h3>Sensibilidade por perturbação</h3>
    <p class="small">A mesma matriz é obtida perturbando a potência de cada nó no
    próprio OpenDSS e medindo a variação de tensão. Um simulador só, e o método
    não depende de o solver expor o jacobiano.</p>
    <p class="small" style="margin:0"><strong>Validação:</strong> erro relativo
    mediano de <strong>0,04%</strong> contra o jacobiano de referência.</p>
  </div>
</div>
<p class="small muted" style="margin-top:1.2rem">Foi acrescentada também a
sensibilidade ao <strong>reativo</strong>, que a formulação original despreza. Ela
não muda o caso da tese, mas mostra que a hipótese é condicional: se o inversor
mantiver fator de potência constante, ignorar o reativo leva de 5 para
<strong>117</strong> pontos violados.</p>
""")

# ---------------------------------------------------------------------------
# 14. Os ciclos
# ---------------------------------------------------------------------------
slide("""
<p class="eyebrow"><span class="dot"></span>O mercado em operação</p>
<h2>Três ciclos de mensagens, dentro de cada janela de 15 minutos</h2>
<div class="cols-3">
  <div class="card"><span class="tag">minuto 1</span>
    <h3>Concentrador &rarr; prosumidores</h3>
    <p class="small" style="margin:0">Cada concentrador pede a programação aos
    prosumidores sob o seu transformador.</p></div>
  <div class="card"><span class="tag">minuto 5</span>
    <h3>DSO &rarr; concentradores</h3>
    <p class="small" style="margin:0">O DSO recolhe as programações agregadas e
    verifica as restrições da rede.</p></div>
  <div class="card"><span class="tag">minuto 10</span>
    <h3>Mercado &rarr; concentradores e DSO</h3>
    <p class="small" style="margin:0">Se houve violação, abre-se a descoberta de
    preço, que itera até o acordo.</p></div>
</div>
<div class="card" style="margin-top:1.6rem">
  <span class="tag">achado</span>
  <p class="small" style="margin:0">O ciclo 2 <strong>não existia como
  tráfego</strong>: o agente de mercado lia a programação direto da memória do
  concentrador, por dentro do processo. O atalho pulava a rede inteira, e por isso
  o ciclo 2 nunca aparecia em medição nenhuma de comunicação. Hoje ele é uma
  troca de mensagens de verdade, iniciada pelo DSO, como a arquitetura descreve.</p>
</div>
""")

# ---------------------------------------------------------------------------
# 15. Resultado principal
# ---------------------------------------------------------------------------
slide("""
<p class="eyebrow"><span class="dot"></span>Resultado principal</p>
<h2>A negociação elimina a subtensão</h2>
<div class="hero-number">
  <span class="big" style="color:var(--amber)">337</span>
  <span class="arrow">&rarr;</span>
  <span class="big" style="color:var(--green)">0</span>
  <span class="stat" style="margin-left:.6rem">
    <span class="l" style="max-width:26ch">pontos abaixo de 0,97 pu, no fluxo de
    potência não linear completo do OpenDSS</span></span>
</div>
<div class="tw">
<table>
  <thead><tr><th>Caso</th><th class="num">Tensão mínima</th><th class="num">Tensão máxima</th><th class="num">Pontos violados</th></tr></thead>
  <tbody>
    <tr><td>Sem mecanismo de mercado</td><td class="num">0,93946 pu</td><td class="num">1,02488 pu</td><td class="num"><span class="bad">337</span></td></tr>
    <tr class="hi"><td>Com a negociação multiagente</td><td class="num">0,97033 pu</td><td class="num">1,02282 pu</td><td class="num"><span class="ok">0</span></td></tr>
  </tbody>
</table>
</div>
<p class="small muted" style="margin-top:1.1rem">O horário crítico é
<strong>17:45</strong>, quando a demanda sobe e a geração solar já caiu. É o mesmo
horário que a tese relata, e não por coincidência: sai da mesma curva de carga com
o mesmo dimensionamento por nó.</p>
""")

# ---------------------------------------------------------------------------
# 16. Figura tensão
# ---------------------------------------------------------------------------
slide(f"""
<p class="eyebrow"><span class="dot"></span>Resultado &middot; tensão</p>
<h2>O dia inteiro, com e sem o mercado</h2>
{fig("tensao_mercado",
     "Tensão mínima e máxima da rede ao longo das 24 horas. A faixa cinza é a "
     "banda operacional de 0,97 a 1,03 pu. Sem negociação, a mínima mergulha "
     "abaixo do limite no fim da tarde; com negociação, ela encosta no limite e "
     "não o cruza.")}
<p class="small muted" style="margin-top:1rem">Repare que o mercado
<strong>não</strong> afasta a tensão do limite mais do que o necessário: ele
resolve a violação ao custo mínimo, que é exatamente o que a função objetivo pede.</p>
""", "fig-slide")

# ---------------------------------------------------------------------------
# 17. Figura programação
# ---------------------------------------------------------------------------
slide(f"""
<p class="eyebrow"><span class="dot"></span>Resultado &middot; como o agente atuou</p>
<h2>A negociação, rodada a rodada, num nó</h2>
{fig("programacao_no",
     "Programação do armazenamento no nó 54, o de maior discordância. Em cima, o "
     "que o concentrador propõe; embaixo, o que o DSO aceita. As cores vão da "
     "primeira rodada à última.")}
<p class="small muted" style="margin-top:1rem">O padrão é o esperado de um
armazenamento que responde a preço: <strong>carrega de madrugada</strong>, quando
a energia é barata, e <strong>descarrega no fim da tarde</strong>, quando é cara e
a rede está no pior momento. O movimento entre rodadas é quase todo no início; daí
as rodadas serem espaçadas em escala logarítmica na figura.</p>
""", "fig-slide")

# ---------------------------------------------------------------------------
# 18. Figura DLMP
# ---------------------------------------------------------------------------
slide(f"""
<p class="eyebrow"><span class="dot"></span>Resultado &middot; preço</p>
<h2>Onde e quando o preço apareceu</h2>
{fig("dlmp",
     "Adicional de preço por nó e por hora, descoberto na negociação. Quanto mais "
     "escuro, maior o sinal.")}
<p class="small muted" style="margin-top:1rem">O preço não é uniforme: concentra-se
nos nós 16 a 28 e em dois horários, a madrugada e o fim da tarde. São exatamente os
momentos em que a rede aperta. Onde não há conflito, o adicional é zero.</p>
<p class="small" style="margin-top:.6rem"><strong>Ressalva honesta:</strong> a
própria tese diz que não trata &lambda; como valor financeiro real, e a formulação
confirma: com o peso adimensional adotado, &lambda; tem unidade de potência, não de
moeda. Por isso a legenda diz <em>sinal</em>. Vira preço quando o peso for
calibrado em unidade monetária.</p>
""", "fig-slide")

# ---------------------------------------------------------------------------
# 19. Convergência
# ---------------------------------------------------------------------------
slide(f"""
<p class="eyebrow"><span class="dot"></span>Resultado &middot; convergência</p>
<h2>O acordo é medido, não declarado</h2>
{fig("convergencia",
     "À esquerda, a discordância entre concentrador e DSO caindo ao longo das "
     "rodadas. À direita, o preço sombra estabilizando.")}
<p class="small muted" style="margin-top:1rem">O critério de parada da formulação
original compara a <strong>variação</strong> do preço, e não a discordância em si.
Isso é um resíduo escalado pelo passo, e com passo decrescente ele dispara cedo
demais: a curva verde declara convergência com discordância cinco vezes pior que a
azul. Reportamos os dois lado a lado, e a comparação honesta é pela discordância.</p>
""", "fig-slide")

# ---------------------------------------------------------------------------
# 20. Comunicação: a rede
# ---------------------------------------------------------------------------
slide("""
<p class="eyebrow"><span class="dot"></span>A camada de comunicação</p>
<h2>A rede que carrega a negociação</h2>
<div class="cols-2">
  <div>
    <p>Uma rede <strong>LPWA 6TiSCH</strong>, sem fio, de baixa potência: o padrão
    IEEE 802.15.4g a 50 kbps, com salto de canal e acesso por divisão de tempo.</p>
    <p class="small">Cada enlace recebe uma taxa de erro que depende da distância,
    pelo modelo de propagação Pister-Hack. As mensagens são roteadas por múltiplos
    saltos até o destino, e o atraso sai da própria simulação de eventos no
    OMNeT++.</p>
  </div>
  <div class="cols" style="grid-template-columns:1fr 1fr">
    <div class="stat"><span class="n blue">578</span><span class="l">enlaces viáveis entre os 77 agentes</span></div>
    <div class="stat"><span class="n">3,18</span><span class="l">saltos em média por mensagem</span></div>
    <div class="stat"><span class="n">4,04 s</span><span class="l">para percorrer um slotframe de 101 timeslots</span></div>
    <div class="stat"><span class="n">127 B</span><span class="l">por quadro, o máximo do padrão</span></div>
  </div>
</div>
<p class="small muted" style="margin-top:1.4rem">As coordenadas dos agentes e a
matriz de adjacência são <strong>dados publicados</strong> pela tese, lidos do
arquivo. Numa primeira versão nós a regenerávamos, o que exige supor o orçamento
de rádio: a suposição natural produziu uma rede duas vezes e meia mais densa, e
resultados de comunicação otimistas.</p>
""")

# ---------------------------------------------------------------------------
# 21. Figura tisch
# ---------------------------------------------------------------------------
slide(f"""
<p class="eyebrow"><span class="dot"></span>Comunicação &middot; alcance</p>
<h2>Erro de pacote em função da distância</h2>
{fig("tisch_per",
     "À esquerda, a taxa de erro de cada par de agentes em função da distância, "
     "separando quem tem enlace de quem não tem. À direita, a fração de pares "
     "com enlace por faixa de distância.")}
<p class="small muted" style="margin-top:1rem">O espalhamento vertical é o próprio
modelo: a mesma distância pode dar erro alto ou baixo, conforme o desvio de
propagação sorteado para aquele par. O alcance efetivo da rede cai rápido:
<strong>84% dos pares se conectam até 100 m</strong>, e praticamente nada além de
500 m.</p>
""", "fig-slide")

# ---------------------------------------------------------------------------
# 22. Figura ciclos
# ---------------------------------------------------------------------------
slide(f"""
<p class="eyebrow"><span class="dot"></span>Comunicação &middot; tempo</p>
<h2>Cada ciclo cabe na sua fatia de tempo?</h2>
{fig("ciclos",
     "Tempo de rede consumido por cada ciclo, contra a fatia que ele tem dentro "
     "da janela de 15 minutos. Escala logarítmica.")}
<p class="small muted" style="margin-top:1rem">Isoladamente, os três cabem. O
aperto é que o ciclo 3 <strong>se repete</strong>: são 34 rodadas de descoberta de
preço, e o acumulado passa de 3.000 segundos contra uma fatia de 300. Na
programação do dia seguinte isso não é problema, porque há horas disponíveis. Na
operação em tempo real, cabem cerca de cinco rodadas.</p>
""", "fig-slide")

# ---------------------------------------------------------------------------
# 23. O achado da comunicação
# ---------------------------------------------------------------------------
slide("""
<p class="eyebrow"><span class="dot"></span>O achado que só a co-simulação revela</p>
<h2>A mensagem real não cabe na rede projetada para ela</h2>
<div class="cols-2">
  <div>
    <p>A implementação de referência informa ao simulador de rede um tamanho de
    mensagem <strong>arbitrário</strong>: 100 bytes para a chamada, 1000 a 1500
    para a proposta. Para a fase de operação isso está certo, e nós medimos 1.004
    bytes.</p>
    <p>Mas a programação do dia seguinte carrega o preço de <strong>25 nós por 96
    intervalos</strong> a cada rodada. O conteúdo real é de
    <strong>35.663 bytes</strong>, ou 281 quadros.</p>
  </div>
  <div class="tw">
    <table>
      <thead><tr><th>Mensagem</th><th class="num">Quadros</th><th class="num">Perda no pior enlace</th></tr></thead>
      <tbody>
        <tr><td>Chamada declarada, 100 B</td><td class="num">1</td><td class="num">2,56%</td></tr>
        <tr><td>Proposta declarada, 1250 B</td><td class="num">10</td><td class="num">22,84%</td></tr>
        <tr><td>Proposta real, 27.275 B</td><td class="num">215</td><td class="num"><span class="bad">99,62%</span></td></tr>
        <tr class="hi"><td>Chamada real, 35.663 B</td><td class="num">281</td><td class="num"><span class="bad">99,93%</span></td></tr>
      </tbody>
    </table>
  </div>
</div>
<p style="margin-top:1.3rem">Perder qualquer fragmento perde a mensagem inteira.
Um enlace tolerável para um quadro é fatal para 281, e o concentrador que fica
atrás dele <strong>se torna incomunicável</strong>: a negociação não completa.</p>
<p class="small" style="margin-top:.4rem"><strong>O número de projeto:</strong> a
chamada precisaria encolher de 35,7 kB para cerca de <strong>500 bytes</strong>,
um fator de 70. Enviar só o que mudou, ou só a parcela do nó destinatário, deixa
de ser refinamento e vira requisito.</p>
""")

# ---------------------------------------------------------------------------
# 24. Validação
# ---------------------------------------------------------------------------
slide("""
<p class="eyebrow"><span class="dot"></span>Validação</p>
<h2>O que confere com a referência</h2>
<div class="tw">
<table>
  <thead><tr><th>Grandeza</th><th class="num">Tese</th><th class="num">Aqui</th><th>Situação</th></tr></thead>
  <tbody>
    <tr><td>Tensão às 17:45, sem e com armazenamento</td><td class="num">0,94 &rarr; 0,97 pu</td><td class="num">0,93946 &rarr; 0,97033 pu</td><td><span class="ok">confere</span></td></tr>
    <tr><td>Horário crítico de subtensão</td><td class="num">17:45</td><td class="num">17:45</td><td><span class="ok">confere</span></td></tr>
    <tr><td>Horário crítico de sobretensão</td><td class="num">10:00</td><td class="num">10:00&ndash;11:00</td><td><span class="ok">confere</span></td></tr>
    <tr><td>Enlaces da rede de comunicação</td><td class="num">578</td><td class="num">578</td><td><span class="ok">confere</span></td></tr>
    <tr><td>Modelo de rede elétrica, barra a barra</td><td class="num">&mdash;</td><td class="num">2,08e-5 pu</td><td><span class="ok">validado</span></td></tr>
    <tr><td>Matriz de sensibilidade</td><td class="num">&mdash;</td><td class="num">0,04% mediano</td><td><span class="ok">validado</span></td></tr>
    <tr class="hi"><td>Preço sombra máximo</td><td class="num">2,18</td><td class="num">2,359</td><td>8%, reconciliado</td></tr>
    <tr class="hi"><td>Rodadas até convergir</td><td class="num">8</td><td class="num">9</td><td>reconciliado</td></tr>
  </tbody>
</table>
</div>
<p class="small muted" style="margin-top:1.1rem">As duas últimas linhas exigiram um
experimento próprio: desligar, uma a uma, as diferenças de modelagem que
acrescentamos. O fator dominante era o <strong>modelo estocástico</strong> &mdash;
o prosumidor que decide sob incerteza programa de forma menos agressiva e estressa
menos a rede. E as rodadas eram o <strong>critério de parada</strong>, três ordens
de grandeza mais frouxo na referência.</p>
""")

# ---------------------------------------------------------------------------
# 25. Contribuições
# ---------------------------------------------------------------------------
slide("""
<p class="eyebrow"><span class="dot"></span>O que este trabalho acrescenta</p>
<h2>Além de portar, o que mudou</h2>
<div class="cols">
  <div class="card"><span class="tag">plataforma</span>
    <h3>Um modelo de rede, não dois</h3>
    <p class="small" style="margin:0">A referência mantinha dois modelos da mesma
    rede, que divergiam em transformador e em modelo de carga. Unificados em
    OpenDSS.</p></div>
  <div class="card"><span class="tag">método</span>
    <h3>Sensibilidade por perturbação</h3>
    <p class="small" style="margin:0">Dispensa o segundo simulador e vale para
    rede desequilibrada. Agora também com reativo.</p></div>
  <div class="card"><span class="tag">protocolo</span>
    <h3>Retransmissão e contabilidade própria</h3>
    <p class="small" style="margin:0">O ContractNet do PADE supõe entrega
    instantânea: sem perda nenhuma, só com atraso, o ciclo fechava com 19 das 25
    programações.</p></div>
  <div class="card"><span class="tag">economia</span>
    <h3>Liquidação e preço locacional</h3>
    <p class="small" style="margin:0">A referência propõe os dois mercados e não
    liquida as transações. Aqui elas são registradas, com a unidade declarada.</p></div>
  <div class="card"><span class="tag">rigor</span>
    <h3>Convergência publicada</h3>
    <p class="small" style="margin:0">Curva de convergência com resíduo primal ao
    lado do critério original, o que expõe quando o critério engana.</p></div>
  <div class="card"><span class="tag">engenharia</span>
    <h3>Execução reprodutível</h3>
    <p class="small" style="margin:0">Um contêiner por simulador, comando único, e
    cada figura carimbada com a configuração que a produziu.</p></div>
</div>
""")

# ---------------------------------------------------------------------------
# 26. Próximos passos
# ---------------------------------------------------------------------------
slide("""
<p class="eyebrow"><span class="dot"></span>Próximos passos</p>
<h2>O que vem agora</h2>
<ul class="steps" style="max-width:75ch">
  <li><strong>Reduzir o tamanho das mensagens.</strong> Deixou de ser refinamento:
  a medição mostra que a chamada precisa cair de 35,7 kB para cerca de 500 bytes
  para a rede da referência conseguir carregá-la. É a pendência que muda uma
  conclusão do trabalho.</li>
  <li><strong>Montar o IEEE European LV Test Feeder</strong> como caso principal
  citável. A MVLV75 é o caso de regressão, que serve para comparar com a
  referência; um caso público padrão serve para publicar.</li>
  <li><strong>Decidir a restrição de estado de carga terminal</strong> com o
  orientador. Ela é nossa, não da referência, e sem ela o modelo esvazia a bateria
  no último intervalo, porque a energia guardada não vale nada na função objetivo.</li>
  <li><strong>Reconciliar a documentação do cenário integrado</strong>, que é
  anterior ao mercado e está desatualizada.</li>
</ul>
""")

# ---------------------------------------------------------------------------
# 27. Fecho
# ---------------------------------------------------------------------------
slide("""
<p class="eyebrow"><span class="dot"></span>Em uma frase</p>
<h2>O mercado transativo saiu do papel e entrou na rede</h2>
<p class="lead">Trinta e três agentes negociam a programação do armazenamento de um
dia inteiro, o preço emerge da disputa em vez de ser arbitrado, e a subtensão que
existiria em 337 pontos da rede desaparece &mdash; com as mensagens passando por
uma rede de comunicação sem fio que atrasa, perde pacote e às vezes não entrega.</p>
<div class="cols" style="margin-top:2rem;max-width:900px">
  <div class="stat"><span class="n green">0</span><span class="l">violações de tensão após a negociação</span></div>
  <div class="stat"><span class="n blue">2,08e-5 pu</span><span class="l">erro do modelo elétrico contra a referência</span></div>
  <div class="stat"><span class="n">8%</span><span class="l">diferença no preço sombra, com causa medida</span></div>
</div>
<p class="small muted" style="margin-top:2rem">Documentação completa no repositório:
<code>MERCADO.md</code> para a formulação, <code>COMPARACAO_TESE.md</code> para o
confronto com a referência, <code>GUIA.md</code> para quem chega agora.</p>
""")

BODY = "\n".join(SLIDES)

LOGO = FIGS["_logo"]
RATIO = f'{FIGS["_logo_ratio"]:.4f}'
CSS = CSS.replace("RATIO", RATIO)
CSS += f'\n.logo {{ -webkit-mask-image: url("{LOGO}"); mask-image: url("{LOGO}"); }}\n'

HTML = f"""<title>Mercado Transativo na MVLV75</title>
<style>{CSS}</style>
<main class="deck" id="deck">
{BODY}
</main>
<div class="rail"><div class="fill" id="fill"></div></div>
<div class="counter" id="counter">1 / {len(SLIDES)}</div>
<div class="hint" id="hint">&larr; &rarr; para navegar</div>
<script>
(function () {{
  var deck = document.getElementById('deck');
  var slides = Array.prototype.slice.call(deck.querySelectorAll('.slide'));
  var fill = document.getElementById('fill');
  var counter = document.getElementById('counter');
  var hint = document.getElementById('hint');
  var current = 0;

  function refresh() {{
    var mid = deck.scrollTop + deck.clientHeight / 2;
    for (var i = 0; i < slides.length; i++) {{
      if (slides[i].offsetTop <= mid &&
          slides[i].offsetTop + slides[i].offsetHeight > mid) {{ current = i; break; }}
    }}
    counter.textContent = (current + 1) + ' / ' + slides.length;
    fill.style.width = ((current + 1) / slides.length * 100) + '%';
  }}

  function go(i) {{
    current = Math.max(0, Math.min(slides.length - 1, i));
    slides[current].scrollIntoView({{behavior: 'smooth', block: 'start'}});
    if (hint) {{ hint.style.opacity = '0'; }}
  }}

  deck.addEventListener('scroll', refresh, {{passive: true}});
  document.addEventListener('keydown', function (e) {{
    if (e.key === 'ArrowRight' || e.key === 'PageDown' || e.key === ' ') {{
      e.preventDefault(); go(current + 1);
    }} else if (e.key === 'ArrowLeft' || e.key === 'PageUp') {{
      e.preventDefault(); go(current - 1);
    }} else if (e.key === 'Home') {{ e.preventDefault(); go(0); }}
    else if (e.key === 'End') {{ e.preventDefault(); go(slides.length - 1); }}
  }});
  refresh();
  setTimeout(function () {{ if (hint) hint.style.opacity = '0'; }}, 6000);
}})();
</script>
"""

out = pathlib.Path(__file__).resolve().parent / "apresentacao_mercado.html"
out.write_text(HTML)
print(f"{out} gravado, {len(HTML)/1e6:.2f} MB, {len(SLIDES)} slides")
