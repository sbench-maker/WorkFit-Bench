FROM python:3.12.11-slim-bookworm
ENV DEBIAN_FRONTEND=noninteractive
ENV MPLCONFIGDIR=/tmp/matplotlib

# Install every runtime dependency during the image build; task execution stays offline.
RUN pip install --no-cache-dir \
    contourpy==1.3.0 \
    cycler==0.12.1 \
    fonttools==4.55.3 \
    iniconfig==2.1.0 \
    kiwisolver==1.4.7 \
    numpy==2.1.3 \
    packaging==25.0 \
    pillow==11.0.0 \
    pluggy==1.6.0 \
    Pygments==2.19.2 \
    pyparsing==3.2.0 \
    python-dateutil==2.9.0.post0 \
    pytest==8.4.1 \
    matplotlib==3.9.2 \
    pypdf==6.14.2 \
    six==1.17.0

WORKDIR /root

RUN id -u agent >/dev/null 2>&1 || useradd --create-home --uid 1000 agent && \
    mkdir -p /app /root/data /root/results /home/agent/.claude /home/agent/.codex /home/agent/.opencode /home/agent/.agents /tmp/matplotlib && \
    chmod 755 /root && chown -R agent:agent /root/results /home/agent /tmp/matplotlib

COPY data/ /root/data/
RUN chmod -R a+rX /root/data

COPY environment_manifest.json /opt/task/environment_manifest.json
COPY check_environment.py /opt/task/check_environment.py
RUN python3 /opt/task/check_environment.py --phase build

# Skills are injected by the evaluation framework and are intentionally not baked into the image.
