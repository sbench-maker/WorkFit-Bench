FROM python:3.12.11-slim-bookworm
ENV DEBIAN_FRONTEND=noninteractive

RUN pip install --no-cache-dir \
    pytest==8.4.1 \
    iniconfig==2.1.0 \
    packaging==25.0 \
    pluggy==1.6.0 \
    pygments==2.19.2

WORKDIR /root

RUN id -u agent >/dev/null 2>&1 || useradd --create-home --uid 1000 agent && \
    mkdir -p /app /root/data /root/results /home/agent/.claude /home/agent/.codex /home/agent/.opencode /home/agent/.agents && \
    chmod 755 /root && chown -R agent:agent /root/results /home/agent

# Install the bundled sglang-offline-runtime==1.0.0 package without registry access.
COPY offline_sglang/ /usr/local/lib/python3.12/site-packages/
COPY data/ /root/data/

COPY environment_manifest.json /opt/task/environment_manifest.json
COPY check_environment.py /opt/task/check_environment.py
RUN python3 /opt/task/check_environment.py --phase build

# Skills are injected by the evaluation framework and are intentionally not baked in.
