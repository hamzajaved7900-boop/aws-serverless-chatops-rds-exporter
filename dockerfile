FROM python:3.11-slim

WORKDIR /app

# Dependencies install karein
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Source code copy karein
COPY main.py .

# Container run hone par script chalegi
CMD ["python", "main.py"]