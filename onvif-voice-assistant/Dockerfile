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

# Instalar dependências Python
COPY requirements.txt /tmp/
RUN pip3 install --no-cache-dir -r /tmp/requirements.txt

# Copiar root filesystem (S6-Overlay structure)
COPY rootfs /

