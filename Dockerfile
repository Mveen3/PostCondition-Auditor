FROM python:3.12-slim

# Set the working directory inside the container
WORKDIR /app

COPY requirements.txt .

# 3. Copy source code and data into the container
# This copies 'src' directory to '/app/src'
COPY src/ ./src/

RUN pip install --no-cache-dir -r requirements.txt
