ARG BUILD_FROM
FROM $BUILD_FROM

# Labels obrigatórias para o Home Assistant Supervisor
ARG BUILD_VERSION
LABEL \
  io.hass.version="${BUILD_VERSION}" \
  io.hass.type="addon" \
  io.hass.arch="armhf|aarch64|i386|amd64|armv7"

# Instalar dependências do sistema
RUN apk add --no-cache \
    python3 \
    py3-pip \
    ffmpeg \
    && rm -rf /var/cache/apk/*

# Diretório de trabalho
WORKDIR /app

# Copiar arquivos
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

COPY *.py .
COPY run.sh .
RUN chmod +x run.sh

# Executar
CMD ["/app/run.sh"]

