
# Base Python image
FROM python:3.11.8-slim

# YAHAN HOTA HAI JADUU: MediaPipe ke liye missing C++ libraries install kar rahe hain!
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Requirements install karein
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Baaki ka code copy karein
COPY . .

# Server start command
CMD["python", "app.py"]
