FROM python:3.11.9-slim-bookworm
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 && \
    rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    pytest==8.3.3 \
    openpyxl==3.1.5 \
    pandas==2.2.3 \
    numpy==1.26.4 \
    toad==0.1.5 \
    lightgbm==4.5.0 \
    scikit-learn==1.5.2 \
    joblib==1.4.2 \
    tqdm==4.66.5

WORKDIR /root

RUN id -u agent >/dev/null 2>&1 || useradd --create-home --uid 1000 agent && \
    mkdir -p /app /root/data /root/results /home/agent/.claude /home/agent/.codex /home/agent/.opencode /home/agent/.agents && \
    chmod 755 /root && chown -R agent:agent /root/results /home/agent

COPY data/ /root/data/
COPY environment_manifest.json /opt/task/environment_manifest.json
COPY check_environment.py /opt/task/check_environment.py
RUN python3 /opt/task/check_environment.py --phase build

# Skills are injected by the evaluation framework and are intentionally not baked in.
