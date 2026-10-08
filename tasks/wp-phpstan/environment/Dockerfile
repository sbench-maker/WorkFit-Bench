FROM python:3.12.11-slim-bookworm
ENV DEBIAN_FRONTEND=noninteractive
ENV LC_ALL=C.UTF-8

# PHP validates the submitted sources, Composer runs the existing project gate,
# and Node supports the bundled inspection workflow. All are installed at build time.
RUN apt-get update && apt-get install -y --no-install-recommends \
        composer \
        nodejs \
        php-cli \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir pytest==8.4.1

COPY tooling/wp_phpstan_check.py /opt/task/wp_phpstan_check.py
RUN chmod 755 /opt/task/wp_phpstan_check.py

WORKDIR /root

RUN id -u agent >/dev/null 2>&1 || useradd --create-home --uid 1000 agent && \
    mkdir -p /app /root/data /root/results /home/agent/.claude /home/agent/.codex /home/agent/.opencode /home/agent/.agents && \
    chmod 755 /root && chown -R agent:agent /root/results /home/agent

COPY data/ /root/data/
RUN chmod 755 /root/data/parcelpilot/vendor/bin/phpstan && \
    find /root/data -type d -exec chmod 755 {} + && \
    find /root/data -type f ! -path '*/vendor/bin/phpstan' -exec chmod 644 {} +

COPY environment_manifest.json /opt/task/environment_manifest.json
COPY check_environment.py /opt/task/check_environment.py
RUN python3 /opt/task/check_environment.py --phase build

# Skills are injected by the evaluation framework and are intentionally not baked here.
