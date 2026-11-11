FROM python:3.11-slim

WORKDIR /app

# Ensure unbuffered logs for real-time streaming inspection
ENV PYTHONUNBUFFERED=1
ENV PORT=8000
ENV HOST=0.0.0.0

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY . .

# Expose HTTP port (Render, Railway, Fly dynamically bind their PORT env var)
EXPOSE 8000

CMD ["python", "web_jarvis.py"]
