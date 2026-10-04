FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY ai_agent/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt && useradd --create-home vision
COPY --chown=vision:vision ai_agent ./ai_agent
USER vision
EXPOSE 9000
CMD ["uvicorn", "ai_agent.main:app", "--host", "0.0.0.0", "--port", "9000", "--no-proxy-headers"]
