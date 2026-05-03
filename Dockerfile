# Use a stable, lightweight Python version
FROM python:3.11.8-slim

# THE FIX: Install the missing C++ graphic libraries MediaPipe needs!
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Run Gunicorn smoothly on the port Render expects
CMD ["sh", "-c", "gunicorn app:app --bind 0.0.0.0:${PORT:-10000} --timeout 120 --workers 1 --threads 2"]
