FROM python:3.12.11-slim-bookworm
ENV DEBIAN_FRONTEND=noninteractive

# Verification support is installed at image-build time and pinned exactly.
RUN pip install --no-cache-dir pytest==8.4.1

# The source skill depends on Trailmark. This deterministic trailmark==0.2.0
# compatibility package keeps its code-graph and diagram workflow available offline.
ARG TRAILMARK_PIN="trailmark==0.2.0"
RUN test "$TRAILMARK_PIN" = "trailmark==0.2.0"
COPY tooling/trailmark/src/trailmark/ /usr/local/lib/python3.12/site-packages/trailmark/
COPY tooling/trailmark/trailmark-0.2.0.dist-info/ /usr/local/lib/python3.12/site-packages/trailmark-0.2.0.dist-info/
COPY tooling/trailmark/trailmark /usr/local/bin/trailmark
COPY tooling/uv /usr/local/bin/uv
RUN chmod 755 /usr/local/bin/trailmark /usr/local/bin/uv

WORKDIR /root

RUN id -u agent >/dev/null 2>&1 || useradd --create-home --uid 1000 agent && \
    mkdir -p /app /root/data /root/results /home/agent/.claude /home/agent/.codex /home/agent/.opencode /home/agent/.agents && \
    chmod 755 /root && chown -R agent:agent /root/results /home/agent

COPY data/ /root/data/

COPY environment_manifest.json /opt/task/environment_manifest.json
COPY check_environment.py /opt/task/check_environment.py
RUN python3 /opt/task/check_environment.py --phase build

# Skills are injected by the evaluation framework; do not bake them here.
