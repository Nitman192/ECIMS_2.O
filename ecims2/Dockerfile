FROM python:3.10-slim

WORKDIR /opt/ecims

COPY server/requirements.txt /opt/ecims/server/requirements.txt
RUN pip install --no-cache-dir -r /opt/ecims/server/requirements.txt

COPY server /opt/ecims/server
COPY configs /opt/ecims/configs
COPY .env.production.template /opt/ecims/.env.production.template

ENV PYTHONPATH=/opt/ecims/server
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3).read()"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
