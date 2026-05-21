FROM python:3.12-slim

WORKDIR /app

# Instala o mosaik para ter acesso ao mosaik-api-server
RUN pip install --no-cache-dir mosaik==3.5 mosaik-api_v3

COPY random_sim.py .

# Expõe a porta que o Mosaik Master vai conectar
EXPOSE 5555

# Comando para rodar o simulador em modo servidor (escutando)
# Sintaxe: mosaik-api-server nome_arquivo:NomeClasse --addr host:porta
CMD ["python3", "random_sim.py", "--remote", "0.0.0.0:5555"]
