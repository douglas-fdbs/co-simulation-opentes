# comm-opentes: a rede de comunicação

O OMNeT++ com uma rede LPWA 6TiSCH (`Tisch.cc`, `Tisch.ned`): IEEE 802.15.4g a
50 kbps, TSCH com salto de canal, perda de quadro pelo modelo de Pister-Hack e
roteamento pelo menor número esperado de transmissões. Roda como contêiner `comm`
e responde por ZMQ (porta 5556) às consultas dos agentes: para cada mensagem, o
caminho, o atraso e se ela se perdeu.

Só entra na co-simulação com `NET_BACKEND=omnet`. A topologia é a do IEEE 13
(`grid-opentes/src/data/13Bus/nodes_xy.csv`), e o servidor grava a rede de rádio
que simulou em `tisch_links.csv`, na mesma pasta. A primeira execução compila o
modelo e leva alguns minutos.
