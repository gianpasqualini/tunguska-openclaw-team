ARG OPENCLAW_IMAGE
FROM ${OPENCLAW_IMAGE}
USER root
ARG LOCAL_UID=1000
ARG LOCAL_GID=1000
ARG STACK_APT_PACKAGES=""
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       ca-certificates curl git gh build-essential libgomp1 libssl3 passwd \
       ${STACK_APT_PACKAGES} \
    && rm -rf /var/lib/apt/lists/* \
    && groupmod -o -g "$LOCAL_GID" node \
    && usermod -o -u "$LOCAL_UID" -g "$LOCAL_GID" node \
    && mkdir -p /home/node/.openclaw /home/node/.config/openclaw \
                /home/node/.cache /workspace/project \
    && chown -R node:node /home/node \
    && chown node:node /workspace/project
# Git usa gh e o token da instalação. Nenhuma credencial é gravada na imagem.
RUN git config --system credential.https://github.com.helper '!/usr/bin/gh auth git-credential'
# Acrescente ferramentas específicas da sua stack aqui, em tempo de build.
# O código do projeto será montado em /workspace/project.
USER node
WORKDIR /app
