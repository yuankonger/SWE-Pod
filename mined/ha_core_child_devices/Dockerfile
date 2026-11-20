# Home Assistant Core at its August 2026 toolchain: Python 3.14.5 (`.python-version`), uv 0.12.2 (`requirements.txt`),
# the OS packages and the dependency set its CI installs for the full test run (requirements.txt,
# requirements_all.txt, requirements_test.txt, under homeassistant/package_constraints.txt). The feature's commits
# change none of them. No source: the repository is mounted and run from its own directory.
FROM python:3.14.5-bookworm@sha256:d1552003e0eb6e4a2c57fcc17c1b1f14fca6b00b1b709bb0e4eb82f21bce5c8c
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        bluez ffmpeg libturbojpeg0 libxml2-utils libavcodec-dev libavdevice-dev libavfilter-dev libavformat-dev \
        libavutil-dev libswresample-dev libswscale-dev libudev-dev libpcap-dev libyaml-dev cmake autoconf pkg-config \
    && rm -rf /var/lib/apt/lists/* && pip install --no-cache-dir uv==0.12.2
# Only the files the install reads (the requirements include each other and the constraints by these paths).
COPY .python-version requirements.txt requirements_all.txt requirements_test.txt requirements_test_pre_commit.txt /deps/
COPY homeassistant/package_constraints.txt /deps/homeassistant/
RUN cd /deps && uv venv /venv --python /usr/local/bin/python3.14 \
    && VIRTUAL_ENV=/venv uv pip install -r requirements.txt \
    && VIRTUAL_ENV=/venv uv pip install -r requirements_all.txt -r requirements_test.txt \
    && rm -rf /root/.cache
ENV PATH=/venv/bin:$PATH VIRTUAL_ENV=/venv PYTHONDONTWRITEBYTECODE=1
# The kernel's shell is a login shell, which resets PATH from /etc/profile: put the environment back on it there.
RUN printf 'export PATH=/venv/bin:$PATH VIRTUAL_ENV=/venv\n' > /etc/profile.d/venv.sh
CMD ["bash"]
