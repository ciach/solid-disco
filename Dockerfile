FROM python:3.12-slim

# Install uv for fast, reliable dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app

# 1. Dependency Layer (Cached)
COPY pyproject.toml uv.lock ./
# We need to create a dummy lock file if it doesn't exist to allow the build to proceed initially,
# or we can rely on `uv sync` generating it.
# However, standard practice with uv in docker usually expects a lockfile.
# For now, we'll try to sync. If uv.lock doesn't exist, this might fail if we enforce frozen.
# Let's run without frozen first if lock is missing, or user should generate it.
# Assuming user generates it locally first. I will generate it in a moment.
RUN uv sync --no-dev

# 2. Application Layer
COPY fastmcp_organizer ./fastmcp_organizer

# 3. Environment
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1

# 4. Entrypoint
EXPOSE 3333
ENTRYPOINT ["uv", "run", "fastmcp-organizer"]
CMD ["server"]
