"""Exporta a transcricao da sessao para Markdown legivel.

O .jsonl guarda cada evento da sessao. Aqui ficam apenas as mensagens de
conversa: o que o usuario escreveu e o que o assistente respondeu em texto. As
chamadas de ferramenta e os resultados delas viram uma linha de resumo, porque o
conteudo bruto (saidas de docker, dumps de CSV) ocupa mais que a conversa inteira
e nao ajuda quem for retomar o trabalho.
"""
import json
import pathlib
import re

# A transcricao fica no diretorio de sessoes do Claude Code, uma por sessao.
# Passe o caminho como argumento para exportar outra.
import sys
PADRAO = ("/home/fdouglas/.claude/projects/"
          "-home-fdouglas-Documentos-OpenTES-Integration/"
          "85e443ea-a4cc-4be9-9e4b-2be8facf908d.jsonl")
ORIGEM = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else PADRAO)
DESTINO = pathlib.Path(__file__).resolve().parent / "HISTORICO_CONVERSA.md"

LIMITE_FERRAMENTA = 400   # caracteres de resultado de ferramenta que sobrevivem


def texto_de(conteudo):
    """Extrai o texto de um bloco de conteudo, que pode ser str ou lista."""
    if isinstance(conteudo, str):
        return conteudo
    partes = []
    if isinstance(conteudo, list):
        for c in conteudo:
            if not isinstance(c, dict):
                continue
            if c.get("type") == "text":
                partes.append(c.get("text", ""))
            elif c.get("type") == "thinking":
                continue                       # raciocinio nao entra no export
            elif c.get("type") == "tool_use":
                nome = c.get("name", "?")
                ent = c.get("input", {})
                desc = ent.get("description") or ent.get("command") or ent.get("file_path") or ""
                desc = re.sub(r"\s+", " ", str(desc))[:120]
                partes.append(f"`[ferramenta: {nome}]` {desc}")
            elif c.get("type") == "tool_result":
                bruto = c.get("content")
                t = texto_de(bruto) if not isinstance(bruto, str) else bruto
                t = re.sub(r"\s+", " ", t or "").strip()
                if t:
                    partes.append(f"> resultado: {t[:LIMITE_FERRAMENTA]}"
                                  + (" [...]" if len(t) > LIMITE_FERRAMENTA else ""))
    return "\n\n".join(p for p in partes if p)


def eh_ruido(t):
    """Mensagens de sistema que nao fazem parte da conversa."""
    marcas = ("<system-reminder>", "[SYSTEM NOTIFICATION", "<command-name>",
              "<local-command-stdout>", "Caveat: The messages below",
              "<ide_selection>", "<ide_opened_file>", "This session is being continued",
              "<task-notification>", "Note: /home/", "The following deferred tools",
              "The user sent a new message while you were working")
    return any(m in t for m in marcas)


linhas = ["# Histórico da conversa — implementação do mercado transativo", "",
          "Exportação da sessão de trabalho no repositório `co-simulation-opentes`,",
          "de 20 de julho a 14 de agosto de 2026.", "",
          "Cada turno do assistente é agrupado num bloco só. As chamadas de",
          "ferramenta aparecem como uma linha de resumo e os resultados vêm",
          "truncados: o conteúdo bruto (saídas de contêiner, dumps de CSV) supera em",
          "muito o texto da conversa e atrapalha a leitura.", "",
          "---", ""]

# Agrupa turnos: tudo que o assistente produz entre duas falas do usuario vira um
# bloco unico. Sem isso, cada chamada de ferramenta virava uma secao propria e o
# documento ficava com mais de mil cabecalhos.
turnos = []          # (quem, [pedacos])
for linha in ORIGEM.open():
    try:
        d = json.loads(linha)
    except Exception:
        continue
    if d.get("type") not in ("user", "assistant"):
        continue
    t = texto_de((d.get("message") or {}).get("content"))
    if not t or not t.strip():
        continue
    quem = d["type"]
    if quem == "user":
        if eh_ruido(t) or t.lstrip().startswith("> resultado:"):
            continue
    if turnos and turnos[-1][0] == quem:
        turnos[-1][1].append(t.strip())
    else:
        turnos.append((quem, [t.strip()]))

n_user = sum(1 for q, _ in turnos if q == "user")
for i, (quem, pedacos) in enumerate(turnos):
    if quem == "user":
        linhas.append(f"## Douglas\n\n{chr(10).join(pedacos)}\n")
    else:
        corpo = "\n\n".join(pedacos)
        linhas.append(f"### Claude\n\n{corpo}\n")

DESTINO.write_text("\n".join(linhas))
print(f"{DESTINO}")
print(f"  {n_user} turnos do usuario, {len(turnos)-n_user} turnos do assistente, "
      f"{DESTINO.stat().st_size/1e6:.2f} MB")
