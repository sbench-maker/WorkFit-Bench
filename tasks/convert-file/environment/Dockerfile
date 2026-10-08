FROM python:3.12.11-slim-bookworm
ENV DEBIAN_FRONTEND=noninteractive
ENV LC_ALL=C.UTF-8

# Pin every Python dependency at image-build time so runtime remains offline.
RUN pip install --no-cache-dir duckdb==1.4.1 pyarrow==17.0.0 pytest==8.4.1

# The source workflow expects a `duckdb -c` command. This thin command uses the
# pinned DuckDB engine and needs no runtime downloads.
COPY duckdb_cli.py /usr/local/bin/duckdb
RUN chmod 755 /usr/local/bin/duckdb

WORKDIR /root

# Pre-create benchmark mount points and skill-injection homes.
RUN id -u agent >/dev/null 2>&1 || useradd --create-home --uid 1000 agent && \
    mkdir -p /app /root/data /root/results /home/agent/.claude /home/agent/.codex /home/agent/.opencode /home/agent/.agents && \
    chmod 755 /root && chown -R agent:agent /root/results /home/agent

# Frozen local inputs; the Docker build context is environment/.
COPY data/ /root/data/
RUN chmod -R a+rX /root/data

COPY environment_manifest.json /opt/task/environment_manifest.json
COPY check_environment.py /opt/task/check_environment.py
RUN python3 /opt/task/check_environment.py --phase build

# Skills are injected by the evaluation framework and are not baked into the image.
