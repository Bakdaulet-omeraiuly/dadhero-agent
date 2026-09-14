# Build from the repo root: docker build -f backend/Dockerfile -t dadhero-backend .
# (needs repo root as context so it can COPY dadhero/ alongside backend/)
FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt requirements.txt
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY dadhero/ dadhero/
COPY backend/ backend/
COPY supabase/ supabase/

ENV PYTHONUNBUFFERED=1
EXPOSE 8000

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
