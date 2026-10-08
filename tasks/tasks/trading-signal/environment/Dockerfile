FROM node:22.17.0-bookworm-slim AS node_runtime
FROM python:3.12.11-slim-bookworm
ENV DEBIAN_FRONTEND=noninteractive

COPY --from=node_runtime /usr/local/bin/node /usr/local/bin/node
RUN pip install --no-cache-dir pytest==8.4.1

WORKDIR /root
RUN id -u agent >/dev/null 2>&1 || useradd --create-home --uid 1000 agent && \
    mkdir -p /app /root/data /root/results /home/agent/.claude /home/agent/.codex /home/agent/.opencode /home/agent/.agents && \
    chmod 755 /root && chown -R agent:agent /root/results /home/agent

COPY data/ /root/data/
COPY environment_manifest.json /opt/task/environment_manifest.json
COPY check_environment.py /opt/task/check_environment.py
RUN python3 /opt/task/check_environment.py --phase build

# Skills are injected by the benchmark harness; do not bake them into the image.
