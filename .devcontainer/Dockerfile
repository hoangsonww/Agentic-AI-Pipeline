# syntax=docker/dockerfile:1.4
ARG VARIANT="3.11"
FROM mcr.microsoft.com/devcontainers/python:${VARIANT}

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
        git \
        pkg-config \
        libxml2-dev \
        libxslt1-dev \
        libsqlite3-dev \
        sqlite3 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Ensure Poetry is available system-wide for dependency management
RUN pip install --no-cache-dir "poetry==1.8.3"

# Create workspace directory owned by the non-root user for proper permissions
ARG USERNAME=vscode
RUN mkdir -p /workspaces \
    && chown "${USERNAME}:${USERNAME}" /workspaces
