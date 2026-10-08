FROM hashicorp/terraform:1.9.8 AS terraform-bin
FROM python:3.12.11-slim-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    TF_IN_AUTOMATION=1 \
    CHECKPOINT_DISABLE=1

COPY --from=terraform-bin /bin/terraform /usr/local/bin/terraform
RUN python3 -m pip install --no-cache-dir pytest==8.4.1

WORKDIR /root

RUN id -u agent >/dev/null 2>&1 || useradd --create-home --uid 1000 agent && \
    mkdir -p /app /root/data /root/results \
      /home/agent/.claude /home/agent/.codex /home/agent/.opencode /home/agent/.agents && \
    chmod 755 /root && \
    chown -R agent:agent /root/results /home/agent

COPY data/ /root/data/
RUN chmod -R a+rX /root/data

COPY environment_manifest.json /opt/task/environment_manifest.json
COPY check_environment.py /opt/task/check_environment.py
RUN python3 /opt/task/check_environment.py --phase build

# Skills are injected by the evaluation framework and are intentionally not baked into the image.
