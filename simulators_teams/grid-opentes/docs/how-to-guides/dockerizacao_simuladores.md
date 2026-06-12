# Dockerização dos simuladores

Este guia documenta a implementação da dockerização dos simuladores do projeto e como executar o cenário Docker corretamente.

## Visão geral

A dockerização foi montada em torno de três peças:

- [Dockerfile](../../Dockerfile)
- [docker-compose.yml](../../docker-compose.yml)
- [src/scenarios/cenariodocker.py](../../src/scenarios/cenariodocker.py)

O padrão adotado é o seguinte:

1. Cada simulador roda em um container próprio.
2. Cada container expõe uma porta TCP fixa para o handshake com o Mosaik.
3. O cenário principal roda no host Windows e conecta nos simuladores via `localhost`.
4. Os arquivos de dados e resultados são compartilhados por volumes.

## Arquivos adicionados na dockerização

Para viabilizar a execução em container, o projeto passou a ter:

- [src/simulators/opendss_simulator.py](../../src/simulators/api_opendss.py) como camada de compatibilidade para cenários antigos
- [src/simulators/api_opendss.py](../../src/simulators/1_api_opendss.py) como implementação principal do OpenDSS
- blocos `if __name__ == '__main__':` nos simuladores que precisam subir como processo remoto no container

Esse bloco final é o que faz cada simulador iniciar o servidor do Mosaik quando o container sobe com `--remote`. Sem isso, o arquivo apenas define a classe do simulador e não fica disponível para conexão via TCP.

## Dockerfile

O [Dockerfile](../../Dockerfile) define a imagem base usada por todos os simuladores:

- imagem `python:3.12-slim`
- instalação de dependências de sistema com `apt`
- instalação das dependências Python a partir de `requirements.txt`
- cópia do diretório `src/`
- definição de `PYTHONPATH=/app/src`

Esse `PYTHONPATH` é importante porque permite importar os módulos do projeto como `simulators.*` dentro do container.

## docker-compose

O [docker-compose.yml](../../docker-compose.yml) cria um serviço por simulador.

### Serviços e portas

- `opendss` -> `5671`
- `battery` -> `5672`
- `collector` -> `5673`
- `controller` -> `5674`
- `csv-data-1` -> `5675`
- `csv-data-2` -> `5676`
- `inverter-std` -> `5677`
- `pv-panel` -> `5678`
- `regulator` -> `5679`
- `smart-inverter` -> `5680`

### Comando de cada container

Cada serviço inicia um simulador com a flag `--remote` apontando para `0.0.0.0:<porta>`.

Isso é essencial porque o simulador remoto não inicia a simulação sozinho; ele abre um servidor TCP e fica aguardando a conexão do Mosaik.

### Volumes montados

Os volumes principais são:

- `./src:/app/src` para montar o código do projeto dentro do container
- `./output:/app/output` para persistir os resultados gerados pelo coletor

## Cenário Docker

O [cenariodocker.py](../../src/scenarios/cenariodocker.py) é o cenário que orquestra a execução.

Ele faz três coisas importantes:

1. Valida os caminhos no host, principalmente o arquivo DSS usado no cenário 123Bus.
2. Declara a configuração de conexão com cada simulador remoto.
3. Cria as entidades, faz as conexões e executa a simulação.

### Configuração de caminhos

O cenário trabalha com caminhos diferentes para host e container:

- no host, o DSS fica em `src/data/123Bus`
- no container, o mesmo arquivo fica em `/app/src/data/123Bus`
- os resultados vão para `src/output` no host e `/app/output` no container

### Fluxo do cenário

O fluxo geral é este:

1. O host sobe o `cenariodocker.py`.
2. O Mosaik tenta conectar em `localhost:5671`, `5673`, `5675`, `5676`, `5677` e `5678`.
3. Os containers já estão em modo de espera por causa do `--remote`.
4. O cenário instancia a rede, cria os elementos e conecta painéis, inversor, OpenDSS e coletor.
5. O coletor escreve os resultados em `/app/output`, que aparecem no host via volume.

## Como executar

### 1. Buildar (construir) a imagem

Abra o terminal na pasta raiz do projeto e execute:

```bash
docker build -t opentes-simulador .
```

Isso cria a imagem `opentes-simulador`. Com a imagem pronta, o próximo passo é subir os serviços no Docker Compose usando essa mesma imagem para cada simulador e sua respectiva porta.

Esse build normalmente é feito apenas na primeira vez que você for rodar. Depois disso, só refaça quando houver mudanças no `Dockerfile`, no `requirements.txt` ou em outra dependência da imagem.

### 2. Subir os containers

```bash
docker compose up
```

### 3. Rodar o cenário no host

Em outro terminal:

```bash
uv run --no-sync python src/scenarios/cenariodocker.py
```

### Execução em segundo plano - Preferencialmente, execute dessa forma

Se preferir deixar os containers rodando em background:

```bash
docker compose up -d
uv run --no-sync python src/scenarios/cenariodocker.py
```

## Onde os arquivos ficam

- Código fonte dentro do container: `/app/src`
- Resultados dentro do container: `/app/output`
- Resultados no host: `output/`

O arquivo de saída principal do cenário 123Bus é:

- `output/result_run_ieee123_cosim_pv_5min.csv`

## Problemas comuns

### O container `opendss` sai com código 0

Isso normalmente significa que o simulador remoto não foi iniciado pelo entrypoint correto. O serviço `opendss` deve executar o módulo compatível `simulators.opendss_simulator` com `--remote`.

### O cenário não conecta em `localhost:5671`

Verifique se:

- os containers estão realmente em execução
- o `docker-compose.yml` foi carregado sem erros
- o cenário foi executado depois que os simuladores subiram

### O resultado não aparece no host

Confirme se o volume `./output:/app/output` está presente no serviço `collector`.

## Observação sobre compatibilidade

O módulo [src/simulators/opendss_simulator.py](../../src/simulators/api_opendss.py) existe como camada de compatibilidade para manter os cenários antigos funcionando, mesmo com a implementação real em `api_opendss.py`.
