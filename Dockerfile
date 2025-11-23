FROM python:3.12-slim

# Set the working directory inside the container
WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# 3. Copy source code and data into the container
COPY src/ ./src/

# Create necessary directories
RUN mkdir -p src/dataset src/reports src/reports/visualizations

# Default command (interactive shell)
CMD ["/bin/bash"]