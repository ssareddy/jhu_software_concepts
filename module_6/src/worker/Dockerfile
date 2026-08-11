FROM python:3.11-slim
WORKDIR /app

# Chromium + matching chromedriver for the Selenium-based scraper.
# Installed as root, before switching to the non-root USER below, so
# nothing needs to be downloaded/written at runtime — Selenium Manager's
# auto-download fails under the non-root container user with a
# "Permission denied" error trying to write its cache directory.
# CHROME_BIN / CHROMEDRIVER_PATH tell _build_driver() to use these exact
# binaries instead of attempting that auto-detection.
RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium \
    chromium-driver \
    && rm -rf /var/lib/apt/lists/*
ENV CHROME_BIN=/usr/bin/chromium
ENV CHROMEDRIVER_PATH=/usr/bin/chromedriver

# A bare numeric USER (see below) has no /etc/passwd entry. Chromium's
# glib-based startup calls getpwuid() to resolve the user's home
# directory/name, and with no matching entry it hits a fatal CHECK and
# crashes immediately (SIGTRAP) — even with --no-sandbox. useradd gives
# uid 1000 a real passwd entry and a writable $HOME.
RUN useradd --uid 1000 --create-home --shell /usr/sbin/nologin appuser
ENV HOME=/home/appuser

# Install the shared gradcafe_common package first — see src/common/ and
# the matching comment in src/web/Dockerfile.
COPY src/common /tmp/common
RUN pip install --no-cache-dir /tmp/common

COPY src/worker/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/worker/ .
USER appuser
CMD ["python", "consumer.py"]