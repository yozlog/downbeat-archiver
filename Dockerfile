FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app
COPY pyproject.toml README.md ./
COPY downbeat_archiver ./downbeat_archiver
RUN pip install --no-cache-dir .

RUN useradd --create-home --uid 1000 archiver && mkdir -p /archive && chown archiver:archiver /archive
USER archiver

VOLUME ["/archive"]
ENTRYPOINT ["downbeat-archiver"]
CMD ["schedule", "--output", "/archive", "--day", "1", "--hour", "3", "--timezone", "Asia/Taipei"]
