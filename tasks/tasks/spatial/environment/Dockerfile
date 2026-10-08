FROM python:3.12.11-slim-bookworm
ENV DEBIAN_FRONTEND=noninteractive
ENV LC_ALL=C.UTF-8

# Pin all Python dependencies while the image is built.
RUN pip install --no-cache-dir duckdb==1.4.1 pytest==8.4.1

# The source workflow expects a duckdb -c command. The wrapper uses the pinned
# engine, and the spatial extension is downloaded once at image-build time.
COPY duckdb_cli.py /usr/local/bin/duckdb
RUN chmod 755 /usr/local/bin/duckdb && \
    duckdb -c "INSTALL spatial; LOAD spatial; SELECT ST_AsText(ST_Point(0, 0));"

WORKDIR /root

RUN id -u agent >/dev/null 2>&1 || useradd --create-home --uid 1000 agent && \
    mkdir -p /app /root/data /root/results /home/agent/.claude /home/agent/.codex /home/agent/.opencode /home/agent/.agents && \
    chmod 755 /root && chown -R agent:agent /root/results /home/agent

COPY data/ /root/data/
RUN chmod -R a+rX /root/data && \
    mkdir -p /home/agent/.duckdb/extensions && \
    cp -R /root/.duckdb/extensions/. /home/agent/.duckdb/extensions/ && \
    chown -R agent:agent /home/agent/.duckdb

COPY environment_manifest.json /opt/task/environment_manifest.json
COPY check_environment.py /opt/task/check_environment.py
RUN python3 /opt/task/check_environment.py --phase build

# Skills are injected by the evaluation framework and are not baked into the image.
