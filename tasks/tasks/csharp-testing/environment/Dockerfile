FROM mcr.microsoft.com/dotnet/sdk:8.0.419-bookworm-slim
ENV DEBIAN_FRONTEND=noninteractive
ENV DOTNET_CLI_HOME=/tmp/dotnet-home \
    DOTNET_NOLOGO=1 \
    DOTNET_SKIP_FIRST_TIME_EXPERIENCE=1 \
    NUGET_PACKAGES=/opt/nuget \
    NUGET_XMLDOC_MODE=skip

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip && \
    rm -rf /var/lib/apt/lists/*

RUN python3 -m pip install --no-cache-dir --break-system-packages pytest==7.2.1

WORKDIR /root

RUN id -u agent >/dev/null 2>&1 || useradd --create-home --uid 1000 agent && \
    mkdir -p /app /root/data /root/results /opt/nuget /tmp/dotnet-home \
      /home/agent/.claude /home/agent/.codex /home/agent/.opencode /home/agent/.agents && \
    chmod 755 /root && \
    chown -R agent:agent /root/results /home/agent /tmp/dotnet-home

COPY data/ /root/data/

RUN dotnet restore /root/data/ParcelPilot/ParcelPilot.sln \
      --packages /opt/nuget && \
    chmod -R a+rX /root/data /opt/nuget

COPY environment_manifest.json /opt/task/environment_manifest.json
COPY check_environment.py /opt/task/check_environment.py
RUN python3 /opt/task/check_environment.py --phase build

# Skills are injected by the evaluation framework and are intentionally not baked into the image.
