# Usa imagem leve oficial do Python 3.12 Slim
FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# DevSecOps (docker:S6470): Copia apenas o código necessário sem recursão
COPY recommendation_service.py .

# DevSecOps (docker:S6471): Cria usuário não-root e concede permissão
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

CMD ["python", "app.py"]