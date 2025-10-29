# Use an official Python 3.10 image as the base
FROM python:3.10-slim

# Set the working directory inside the container
WORKDIR /app

# Copy the file that lists our Python libraries
COPY requirements.txt .

# Install those libraries
RUN pip install --no-cache-dir -r requirements.txt

# By default, just open a terminal
CMD ["bash"]