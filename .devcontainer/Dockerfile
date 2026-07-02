FROM mcr.microsoft.com/vscode/devcontainers/base:ubuntu

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Google Cloud CLI (https://cloud.google.com/sdk/docs/install#deb)
RUN curl -fsSL https://packages.cloud.google.com/apt/doc/apt-key.gpg | gpg --dearmor -o /usr/share/keyrings/cloud.google.gpg && \
    echo "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] https://packages.cloud.google.com/apt cloud-sdk main" \
      > /etc/apt/sources.list.d/google-cloud-sdk.list && \
    apt-get update && \
    CLOUDSDK_SKIP_PY_COMPILATION=1 apt-get install -y google-cloud-cli && \
    rm -rf /var/lib/apt/lists/*

# gh/gcloud の認証情報を named volume で永続化するためのマウント先を事前作成
RUN mkdir -p /home/vscode/.config/gh /home/vscode/.config/gcloud && \
    chown -R vscode:vscode /home/vscode/.config
