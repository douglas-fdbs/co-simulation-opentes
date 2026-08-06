//
// Rede LPWA 6TiSCH da tese (subsecao 6.1.5), como servidor de roteamento.
//
// O `CoSimulationNetwork` existente e uma nuvem de rede de no unico, com perda
// plana e latencia de dezenas de milissegundos. Esta rede e outra coisa: um
// modelo multi-salto com PER por distancia, que responde consultas de rota vindas
// dos agentes PADE em vez de participar do passo do Mosaik.
//
// Os dois convivem: escolha pela configuracao do omnetpp.ini (`-c General` para a
// nuvem, `-c tisch` para esta).
//
simple TischServer
{
    parameters:
        // Porta ZMQ das consultas de rota. Diferente da 5555 do MosaikBridge de
        // proposito: os dois podem rodar ao mesmo tempo.
        int port = default(5556);
        string positions_file = default("nodes_xy.csv");

        // --- Radio: IEEE 802.15.4g modo 1, banda ISM dos EUA ---------------
        double frequency_hz = default(915e6);
        double tx_power_dbm = default(0.0);
        double tx_gain_db = default(0.0);
        double rx_gain_db = default(0.0);
        // Pister-Hack: o RSSI de espaco livre menos uma uniforme de 0 a 40 dB.
        // Sorteada UMA vez por enlace, porque o modelo descreve a variacao de
        // longo prazo do ambiente de propagacao, nao o desvanecimento por pacote.
        double pister_hack_shift_db = default(40.0);
        double sensitivity_dbm = default(-106.37);

        // --- TSCH ----------------------------------------------------------
        // 101 timeslots, 4,04 s por slotframe. Um cell dedicado por enlace por
        // slotframe e o padrao minimo do 6TiSCH.
        double slotframe_s = default(4.04);
        int cells_per_slotframe = default(1);
        // Frame maximo do IEEE 802.15.4. E o numero da tese; uma pilha real
        // gasta parte disso em cabecalho 802.15.4, 6LoWPAN e UDP, e sobram cerca
        // de 80 bytes uteis, o que aumenta os tempos em cerca de 60%.
        int frame_bytes = default(127);
        // macMaxFrameRetries do IEEE 802.15.4.
        int max_retries = default(3);

        // Um enlace so existe se o PER estiver abaixo deste valor.
        double link_per_threshold = default(0.5);

        // Grava o levantamento dos enlaces para a figura de PER por distancia.
        string links_csv = default("tisch_links.csv");

        @display("i=block/network2");
}

network TischNetwork
{
    submodules:
        tisch: TischServer {
            @display("p=50,50");
        }
}
