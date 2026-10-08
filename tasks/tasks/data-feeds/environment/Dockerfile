FROM node:22.20.0-bookworm-slim AS node_runtime

FROM python:3.12.11-slim-bookworm
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    LC_ALL=C.UTF-8 \
    LANG=C.UTF-8

RUN apt-get update && apt-get install -y --no-install-recommends jq && \
    rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    iniconfig==2.1.0 \
    packaging==25.0 \
    pluggy==1.6.0 \
    Pygments==2.19.2 \
    pytest==8.4.1

# BenchFlow installs its agent with Node from this stable path. Seed that path
# before replacing curl with the task's offline data-feed emulator, so runtime
# bootstrap never tries to download Node through the emulator.
COPY --from=node_runtime /usr/local/bin/node /opt/benchflow/node/bin/node
COPY --from=node_runtime /usr/local/lib/node_modules /opt/benchflow/node/lib/node_modules
RUN ln -s ../lib/node_modules/npm/bin/npm-cli.js /opt/benchflow/node/bin/npm && \
    ln -s ../lib/node_modules/npm/bin/npx-cli.js /opt/benchflow/node/bin/npx && \
    /opt/benchflow/node/bin/node --version && \
    PATH=/opt/benchflow/node/bin:$PATH /opt/benchflow/node/bin/npm --version

WORKDIR /root

RUN id -u agent >/dev/null 2>&1 || useradd --create-home --uid 1000 agent && \
    mkdir -p /app /root/data /root/results /home/agent/.claude /home/agent/.codex /home/agent/.opencode /home/agent/.agents && \
    chmod 755 /root && chown -R agent:agent /root/results /home/agent

COPY data/ /root/data/
RUN install -m 0755 /root/data/mock_curl.py /usr/local/bin/curl && chmod -R a+rX /root/data

COPY environment_manifest.json /opt/task/environment_manifest.json
COPY check_environment.py /opt/task/check_environment.py
RUN python3 /opt/task/check_environment.py --phase build

# Skills are injected by the evaluation framework and are intentionally not baked into the image.
