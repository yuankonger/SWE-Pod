# seedco-toolchain: one image with all four service toolchains, dependencies cached.
# Build:  docker build -t seedco-toolchain:0.1 docker/
FROM mcr.microsoft.com/dotnet/sdk:8.0-bookworm-slim
ENV DEBIAN_FRONTEND=noninteractive DOTNET_CLI_TELEMETRY_OPTOUT=1 DOTNET_NOLOGO=1
RUN apt-get update \
    && apt-get install -y --no-install-recommends openjdk-17-jdk-headless python3 python3-pip curl ca-certificates git \
    && rm -rf /var/lib/apt/lists/*

# Node.js 24 from nodejs.org (runs TypeScript directly; the services use no npm packages)
RUN set -eu; arch=$(dpkg --print-architecture); case "$arch" in arm64) n=arm64;; amd64) n=x64;; *) exit 1;; esac; \
    file=$(curl -fsSL https://nodejs.org/dist/latest-v24.x/SHASUMS256.txt | grep "linux-$n.tar.gz" | awk '{print $2}'); \
    curl -fsSL "https://nodejs.org/dist/latest-v24.x/$file" | tar -xz -C /usr/local --strip-components=1 --wildcards '*/bin/node'; \
    node --version

# The harness talks to the model through the official Anthropic Python SDK
RUN pip3 install --no-cache-dir --break-system-packages anthropic

# Java libraries (no build tool: javac + jars on the classpath)
ARG JACKSON=2.17.2
ARG JUNIT=1.10.3
RUN mkdir -p /opt/jars && cd /opt/jars \
    && for a in jackson-core jackson-databind jackson-annotations; do \
         curl -fsSLO https://repo1.maven.org/maven2/com/fasterxml/jackson/core/$a/$JACKSON/$a-$JACKSON.jar; done \
    && curl -fsSLO https://repo1.maven.org/maven2/org/junit/platform/junit-platform-console-standalone/$JUNIT/junit-platform-console-standalone-$JUNIT.jar

# Warm the NuGet cache with the test packages Billing.Tests uses (same versions as its csproj)
RUN mkdir /tmp/warm && cd /tmp/warm && dotnet new xunit -o t --no-restore >/dev/null \
    && cd t && dotnet add package Microsoft.NET.Test.Sdk -v 17.11.1 --no-restore >/dev/null \
    && dotnet add package xunit -v 2.9.2 --no-restore >/dev/null \
    && dotnet add package xunit.runner.visualstudio -v 2.8.2 --no-restore >/dev/null \
    && dotnet restore >/dev/null && cd / && rm -rf /tmp/warm

WORKDIR /work
