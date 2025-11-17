FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies for image processing and scientific computing
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libc6-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create directories for static files and generated images
RUN mkdir -p static/generated

# Set PYTHONPATH so imports work
ENV PYTHONPATH=/app

# Expose Flask port
EXPOSE 5555

# Run the Flask application
CMD ["python", "app.py"]

