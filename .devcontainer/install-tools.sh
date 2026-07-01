#!/bin/bash
set -e

# Claude Code (binary)
curl -fsSL https://claude.ai/install.sh | bash

# OpenTofu (via tenv; version pinned in .opentofu-version)
TENV_VERSION=$(curl --silent https://api.github.com/repos/tofuutils/tenv/releases/latest | grep -oP '"tag_name": "\K[^"]+')
curl -fsSL -O "https://github.com/tofuutils/tenv/releases/latest/download/tenv_${TENV_VERSION}_amd64.deb"
sudo dpkg -i "tenv_${TENV_VERSION}_amd64.deb"
rm "tenv_${TENV_VERSION}_amd64.deb"
tenv tofu install

# Python dependencies (if pyproject.toml exists)
uv sync --frozen 2>/dev/null || true
