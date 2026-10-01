FROM public.ecr.aws/docker/library/python:3.12-slim-bookworm AS builder
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential default-libmysqlclient-dev pkg-config \
    && rm -rf /var/lib/apt/lists/*
ARG SERVICE_NAME
WORKDIR /app
COPY services/${SERVICE_NAME}/requirements.txt /app/requirements.txt
RUN python -m pip wheel --wheel-dir /wheels -r /app/requirements.txt

FROM public.ecr.aws/docker/library/python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1
RUN apt-get update \
    && apt-get install -y --no-install-recommends libmariadb3 \
    && rm -rf /var/lib/apt/lists/*
ARG SERVICE_NAME
WORKDIR /app
COPY --from=builder /wheels /wheels
COPY services/${SERVICE_NAME}/requirements.txt /app/requirements.txt
RUN python -m pip install --no-index --find-links=/wheels -r /app/requirements.txt \
    && rm -rf /wheels
COPY services/${SERVICE_NAME}/ /app/

RUN groupadd --system app && useradd --system --gid app app \
    && chown -R app:app /app
USER app

CMD ["python", "start.py"]
