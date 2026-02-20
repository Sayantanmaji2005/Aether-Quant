FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md /app/
COPY src /app/src

RUN pip install --upgrade pip && pip install .

ENTRYPOINT ["aetherquant"]
CMD ["signal", "--latest-return", "0.01"]
