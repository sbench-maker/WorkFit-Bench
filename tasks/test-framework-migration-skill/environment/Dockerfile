FROM node:22.17.0-bookworm-slim

ENV DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1 \
    NODE_PATH=/opt/playwright/node_modules \
    PATH=/opt/playwright/node_modules/.bin:${PATH}

RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 \
        python3-pip \
    && rm -rf /var/lib/apt/lists/*

RUN pip3 install --break-system-packages --no-cache-dir pytest==8.4.1
RUN npm install --prefix /opt/playwright --no-audit --no-fund \
        @playwright/test@1.55.0 \
        typescript@5.9.2 && \
    playwright install --with-deps chromium && \
    ln -s "$(find /ms-playwright -type f -path '*/chrome-linux/chrome' | head -n 1)" /usr/local/bin/chromium && \
    chmod -R a+rX /opt/playwright /ms-playwright

# Fail the image build immediately if the pinned browser cannot actually launch.
RUN node -e "const { chromium } = require('/opt/playwright/node_modules/playwright'); (async () => { const browser = await chromium.launch({ headless: true, args: ['--no-sandbox'] }); await browser.close(); })().catch((error) => { console.error(error); process.exit(1); });"

WORKDIR /root

RUN id -u agent >/dev/null 2>&1 || useradd --create-home --uid 1001 agent && \
    mkdir -p /app /root/data /root/results /home/agent/.claude /home/agent/.codex /home/agent/.opencode /home/agent/.agents && \
    chmod 755 /root && chown -R agent:agent /root/results /home/agent

COPY data/ /root/data/
RUN chmod -R a+rX /root/data

COPY environment_manifest.json /opt/task/environment_manifest.json
COPY check_environment.py /opt/task/check_environment.py
RUN python3 /opt/task/check_environment.py --phase build

# Skills are injected by the evaluation framework and are not baked into the image.
