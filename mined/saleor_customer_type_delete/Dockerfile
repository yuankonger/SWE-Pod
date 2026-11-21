# Saleor core at its August 2026 toolchain: Python 3.12, uv, a local PostgreSQL, the system libraries Saleor's own
# Dockerfile installs, and the locked dependencies of the base commit (the target's are identical). No source.
FROM python:3.12-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends postgresql gettext libmagic1 libcairo2 libgdk-pixbuf2.0-0 \
    liblcms2-2 libopenjp2-7 libpango-1.0-0 libpangocairo-1.0-0 libtiff6 libwebp7 libxml2 libpq5 shared-mime-info mime-support \
    && rm -rf /var/lib/apt/lists/* && pip install --no-cache-dir uv
COPY pyproject.toml uv.lock /deps/
RUN cd /deps && UV_PROJECT_ENVIRONMENT=/venv uv sync --frozen --all-groups --no-install-project && rm -rf /root/.cache
ENV PATH=/venv/bin:$PATH DATABASE_URL=postgres://saleor:saleor@127.0.0.1:5432/saleor SECRET_KEY=not-a-secret PYTHONDONTWRITEBYTECODE=1
# The kernel's shell is a login shell, which resets PATH from /etc/profile: put the environment back on it there.
RUN printf 'export PATH=/venv/bin:$PATH\n' > /etc/profile.d/venv.sh
# PostgreSQL runs inside the container, so tests need no network.
RUN printf '#!/bin/bash\nservice postgresql start >/dev/null 2>&1\nsu postgres -c "psql -qc \\"CREATE ROLE saleor SUPERUSER LOGIN PASSWORD '"'"'saleor'"'"'\\" -c '"'"'CREATE DATABASE saleor OWNER saleor'"'"'" >/dev/null 2>&1\nexec "$@"\n' > /entrypoint.sh && chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
CMD ["bash"]
