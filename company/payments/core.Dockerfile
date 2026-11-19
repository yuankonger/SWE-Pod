# The API (Saleor core) of the payment-path company, and the Python sidecars beside it (provider stand-in, setup,
# traffic), which need nothing but this image's Python and openssl. Context: a tree of saleor/saleor plus sidecars/.
FROM python:3.12-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends postgresql gettext libmagic1 libcairo2 libgdk-pixbuf2.0-0 \
    liblcms2-2 libopenjp2-7 libpango-1.0-0 libpangocairo-1.0-0 libtiff6 libwebp7 libxml2 libpq5 shared-mime-info mime-support \
    && rm -rf /var/lib/apt/lists/* && pip install --no-cache-dir uv
COPY core/pyproject.toml core/uv.lock /deps/
RUN cd /deps && UV_PROJECT_ENVIRONMENT=/venv uv sync --frozen --all-groups --no-install-project && rm -rf /root/.cache
ENV PATH=/venv/bin:$PATH DATABASE_URL=postgres://saleor:saleor@127.0.0.1:5432/saleor SECRET_KEY=not-a-secret PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY core /srv/core
COPY sidecars /opt/seedco
WORKDIR /srv/core
