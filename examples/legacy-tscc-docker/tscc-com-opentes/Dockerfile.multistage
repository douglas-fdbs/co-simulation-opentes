ARG PYTHON_VERSION=3.12.11

FROM python:${PYTHON_VERSION}-slim AS tscc-mosaik

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN pip install --no-cache-dir \
    mosaik==3.5.0 \
    mosaik-api-v3==3.0.14 \
    mosaik-csv==2.0.1 \
    pandas \
    matplotlib \
    pyzmq==27.1.0

COPY tscc-com-opentes/mosaik-dir/ /app/

CMD ["sh", "-c", "python star.py && python plot_results_star.py"]

FROM python:${PYTHON_VERSION}-slim AS tscc-pade

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y \
    build-essential \
    gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/pade
COPY tteso-tes-opentes/pyproject.toml tteso-tes-opentes/README.md tteso-tes-opentes/LICENSE ./
COPY tteso-tes-opentes/pade ./pade
RUN pip install --no-cache-dir /opt/pade

WORKDIR /app
RUN pip install --no-cache-dir \
    mosaik-api-v3==3.0.14 \
    pyzmq==27.1.0 \
    ipython==8.26.0

COPY tscc-com-opentes/pade-dir/pade_agents/ /app/

EXPOSE 5678/tcp

CMD ["python3", "pade_star.py"]

FROM omnetpp/omnetpp:u22.04-6.0 AS tscc-omnet

RUN apt-get update && apt-get install -y \
    libzmq5-dev \
    git \
    cmake \
    build-essential \
    nlohmann-json3-dev \
    && rm -rf /var/lib/apt/lists/*

RUN git clone https://github.com/zeromq/cppzmq.git /tmp/cppzmq \
    && cd /tmp/cppzmq \
    && mkdir build \
    && cd build \
    && cmake .. \
    && make install \
    && rm -rf /tmp/cppzmq

WORKDIR /root/models
COPY tscc-com-opentes/omnet-dir/ /root/models/

EXPOSE 5555/tcp

CMD ["bash", "-lc", "source /root/omnetpp/setenv && opp_makemake -f --deep -O out -o sim_exec -lzmq && make && ./sim_exec -u Cmdenv -c General"]
