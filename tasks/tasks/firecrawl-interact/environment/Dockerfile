FROM python:3.12.11-slim-bookworm
RUN pip install --no-cache-dir pytest==8.4.1 && useradd --create-home --shell /bin/bash agent \
    && mkdir -p /app /root/results /home/agent/.claude /home/agent/.codex /home/agent/.opencode /home/agent/.agents \
    && chmod 755 /root && chown -R agent:agent /root/results /home/agent
COPY data/ /root/data/
COPY mock_firecrawl.py /usr/local/bin/firecrawl
COPY environment_manifest.json /opt/task/environment_manifest.json
COPY check_environment.py /opt/task/check_environment.py
RUN chmod 755 /usr/local/bin/firecrawl /opt/task/check_environment.py && chmod -R a+rX /root/data
RUN python3 /opt/task/check_environment.py --phase build
WORKDIR /root
