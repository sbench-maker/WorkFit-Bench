FROM mcr.microsoft.com/dotnet/sdk:8.0.408-bookworm-slim AS dotnet-sdk

FROM python:3.12.11-slim-bookworm
ENV DEBIAN_FRONTEND=noninteractive \
    DOTNET_NOLOGO=1 \
    DOTNET_SKIP_FIRST_TIME_EXPERIENCE=1 \
    NUGET_PACKAGES=/opt/nuget-packages \
    DOTNET_CLI_HOME=/home/agent/.dotnet \
    LANG=C.UTF-8

COPY --from=dotnet-sdk /usr/share/dotnet /usr/share/dotnet
RUN ln -s /usr/share/dotnet/dotnet /usr/local/bin/dotnet && \
    apt-get update && apt-get install -y --no-install-recommends \
      bash ca-certificates fontconfig fonts-dejavu-core fonts-liberation \
      libreoffice-writer pandoc zip unzip && \
    rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
      pytest==8.4.1 \
      python-docx==1.2.0 \
      lxml==5.4.0

RUN id -u agent >/dev/null 2>&1 || useradd --create-home --uid 1000 agent && \
    mkdir -p /app /root/data /root/results /opt/task /opt/nuget-packages \
      /home/agent/.claude /home/agent/.codex /home/agent/.opencode \
      /home/agent/.agents /home/agent/.dotnet && \
    chmod 755 /root && \
    chown -R agent:agent /root/results /home/agent

# Warm the exact NuGet dependencies required by the injected source skill so
# its offline restore/build can complete without baking the skill itself.
COPY nuget-cache/NuGetCache.csproj /tmp/nuget-cache/NuGetCache.csproj
RUN DOTNET_CLI_HOME=/tmp/dotnet-home dotnet restore /tmp/nuget-cache/NuGetCache.csproj \
      --packages /opt/nuget-packages && \
    rm -rf /tmp/nuget-cache /tmp/dotnet-home && \
    chmod -R a+rX /opt/nuget-packages

WORKDIR /root
COPY data/ /root/data/
RUN chmod -R a+rX /root/data

COPY environment_manifest.json /opt/task/environment_manifest.json
COPY check_environment.py /opt/task/check_environment.py
RUN python3 /opt/task/check_environment.py --phase build

# Skills are injected by the evaluation framework at runtime; do not copy them here.
