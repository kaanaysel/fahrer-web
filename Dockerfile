# Offizielles Playwright-Python-Image: Chromium + Ubuntu-Systembibliotheken.
# Version EXAKT identisch mit der Version in requirements.txt.
FROM mcr.microsoft.com/playwright/python:v1.57.0-noble

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

WORKDIR /opt/plus-minus-cloud
COPY requirements.txt ./
RUN python -m pip install --no-cache-dir -r requirements.txt

# Fail fast while building instead of discovering absent Chromium with live payslips.
# No Shiftbase access and no employee data in this self-test.
RUN python - <<'PY'
from importlib.metadata import version
from playwright.sync_api import sync_playwright
assert version('playwright') == '1.57.0', 'Playwright version mismatch'
with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True, args=['--no-sandbox', '--disable-dev-shm-usage'])
    try:
        page = browser.new_page()
        page.goto('about:blank')
        assert page.url == 'about:blank'
    finally:
        browser.close()
print('PLAYWRIGHT_CHROMIUM_BUILD_CHECK_OK')
PY

# Die einzige, bisherige Flask-Anwendung – keine neue Webapp.
COPY cloud_plus_minus_webapp.py ./cloud_plus_minus_webapp.py

# Das vorhandene Render-Volume bleibt bei /var/data gemountet.
ENV PORTAL_DATA_DIR=/var/data
EXPOSE 10000
CMD ["sh", "-c", "exec gunicorn --workers 1 --threads 2 --timeout 150 --bind 0.0.0.0:${PORT:-10000} cloud_plus_minus_webapp:app"]
