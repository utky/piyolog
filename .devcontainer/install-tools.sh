#!/bin/bash
set -e

# Claude Code (binary)
curl -fsSL https://claude.ai/install.sh | bash

# Python dependencies (if pyproject.toml exists)
uv sync --frozen 2>/dev/null || true
