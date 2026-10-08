FROM node:20.19.5-bookworm-slim
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends python3 python3-venv && \
    rm -rf /var/lib/apt/lists/*
RUN python3 -m venv /opt/task-venv && \
    /opt/task-venv/bin/pip install --no-cache-dir pytest==8.4.1 PyYAML==6.0.2
ENV PATH="/opt/task-venv/bin:${PATH}"

WORKDIR /root

RUN id -u agent >/dev/null 2>&1 || useradd --create-home --uid 1001 agent && \
    mkdir -p /app /root/data /root/results /home/agent/.claude /home/agent/.codex /home/agent/.opencode /home/agent/.agents && \
    chmod 755 /root && chown -R agent:agent /root/results /home/agent

COPY data/ /root/data/

COPY environment_manifest.json /opt/task/environment_manifest.json
COPY check_environment.py /opt/task/check_environment.py
RUN python3 /opt/task/check_environment.py --phase build
