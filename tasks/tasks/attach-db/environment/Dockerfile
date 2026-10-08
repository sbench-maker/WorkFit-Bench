FROM python:3.12.11-slim-bookworm
ENV DEBIAN_FRONTEND=noninteractive
ENV LC_ALL=C.UTF-8

# Install the project-root helper used by the source workflow and pin every
# Python dependency while the image is built; runtime remains offline.
RUN apt-get update && apt-get install -y --no-install-recommends git && \
    rm -rf /var/lib/apt/lists/* && \
    pip install --no-cache-dir duckdb==1.4.1 pytest==8.4.1

# The pinned Python engine backs the CLI subset needed by the attachment flow.
COPY duckdb_cli.py /usr/local/bin/duckdb
RUN chmod 755 /usr/local/bin/duckdb

WORKDIR /root

RUN id -u agent >/dev/null 2>&1 || useradd --create-home --uid 1000 agent && \
    mkdir -p /app /root/data /root/results /home/agent/.claude /home/agent/.codex /home/agent/.opencode /home/agent/.agents && \
    chmod 755 /root && chown -R agent:agent /root/results /home/agent

# Frozen local inputs; the Docker build context is environment/.
COPY data/ /root/data/
RUN python3 /root/data/build_databases.py && chmod -R a+rX /root/data

COPY environment_manifest.json /opt/task/environment_manifest.json
COPY check_environment.py /opt/task/check_environment.py
RUN python3 /opt/task/check_environment.py --phase build

# Skills are injected by the evaluation framework and are not baked in here.
