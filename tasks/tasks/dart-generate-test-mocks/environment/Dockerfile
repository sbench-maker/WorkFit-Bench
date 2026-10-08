FROM dart:3.5.4

ENV DEBIAN_FRONTEND=noninteractive \
    PUB_CACHE=/opt/dart-pub-cache

RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-pip \
    && python3 -m pip install --break-system-packages --no-cache-dir pytest==8.3.3 \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --shell /bin/bash agent \
    && mkdir -p /app /root/results /home/agent/.claude /home/agent/.codex /home/agent/.opencode /home/agent/.agents /opt/task "$PUB_CACHE" \
    && chown -R agent:agent /root/results /home/agent \
    && chmod 0755 /root

COPY data/ /root/data/
COPY environment_manifest.json /opt/task/environment_manifest.json
COPY check_environment.py /opt/task/check_environment.py

RUN cd /root/data/reservation_app \
    && dart pub get \
    && chmod -R a+rX /root/data "$PUB_CACHE"

RUN python3 /opt/task/check_environment.py --phase build

WORKDIR /root
