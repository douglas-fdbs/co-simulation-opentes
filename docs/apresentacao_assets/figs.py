import base64, json, pathlib
d = pathlib.Path("/home/fdouglas/Documentos/OpenTES_Integration/co-simulation-opentes/simulators/market-opentes/data")
out = {}
for f in sorted(d.glob("*.png")):
    out[f.stem] = "data:image/png;base64," + base64.b64encode(f.read_bytes()).decode()
pathlib.Path("/tmp/claude-1000/-home-fdouglas-Documentos-OpenTES-Integration/85e443ea-a4cc-4be9-9e4b-2be8facf908d/scratchpad/figs.json").write_text(json.dumps(out))
print(f"{len(out)} figuras, {sum(len(v) for v in out.values())/1e6:.2f} MB em base64")
