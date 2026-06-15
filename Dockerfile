# Imagem para rodar o app SalesOps AI (backend + front glass) no Hugging Face
# Spaces (SDK: docker). O Space expõe a porta 7860.
FROM python:3.11-slim

WORKDIR /app

# Dependências
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Código
COPY salesops ./salesops
COPY server ./server
COPY web ./web

# Onde as lojas/credenciais são salvas. Para persistir entre reinícios no HF,
# habilite "Persistent storage" e deixe SALESOPS_STORE_FILE=/data/stores.json.
ENV SALESOPS_STORE_FILE=/app/data/stores.json
RUN mkdir -p /app/data && chmod 777 /app/data

EXPOSE 7860

CMD ["uvicorn", "server.app:app", "--host", "0.0.0.0", "--port", "7860"]
