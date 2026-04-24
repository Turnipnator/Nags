FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY . .

# Create data/logs dirs
RUN mkdir -p /app/data /app/logs

CMD ["python", "main.py"]
