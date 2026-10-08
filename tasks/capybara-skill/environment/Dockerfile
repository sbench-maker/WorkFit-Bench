FROM python:3.12.11-slim-bookworm
ENV DEBIAN_FRONTEND=noninteractive
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8

RUN apt-get update && apt-get install -y --no-install-recommends ruby-full build-essential && \
    rm -rf /var/lib/apt/lists/*

RUN gem install --no-document \
      rack:3.1.8 \
      rack-test:2.2.0 \
      rspec:3.13.0 \
      capybara:3.40.0 && \
    ruby -e 'require "rack"; require "rack/test"; require "capybara/rspec"' && \
    rspec --version

RUN pip install --no-cache-dir pytest==8.4.1

WORKDIR /root

RUN id -u agent >/dev/null 2>&1 || useradd --create-home --uid 1000 agent && \
    mkdir -p /app /root/data /root/results /home/agent/.claude /home/agent/.codex /home/agent/.opencode /home/agent/.agents && \
    chmod 755 /root && chown -R agent:agent /root/results /home/agent

COPY data/ /root/data/

COPY environment_manifest.json /opt/task/environment_manifest.json
COPY check_environment.py /opt/task/check_environment.py
RUN python3 /opt/task/check_environment.py --phase build

# Skills are injected by the evaluation framework; do not bake them into the image.
