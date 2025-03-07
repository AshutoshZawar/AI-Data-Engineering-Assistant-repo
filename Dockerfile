FROM python:3.9-slim

WORKDIR /app

# Install only critical dependencies (much faster)
COPY docker-requirements.txt .
RUN pip install --no-cache-dir -r docker-requirements.txt

# Copy just the necessary files
COPY src/chatbot/optimized_api.py ./app.py
COPY config.yaml .

# Run the API
CMD ["python", "app.py"]

# Expose API port
EXPOSE 5000

# FROM python:3.9-slim

# WORKDIR /app

# # Install system dependencies
# RUN apt-get update && apt-get install -y --no-install-recommends \
#     gcc \
#     python3-dev \
#     && rm -rf /var/lib/apt/lists/*

# # Copy requirements first for better caching
# COPY requirements.txt .
# RUN pip install --no-cache-dir -r requirements.txt

# # Copy application code
# COPY src/ ./src/
# COPY config.yaml .

# # Create necessary directories
# RUN mkdir -p data

# # Set environment variables
# ENV PYTHONPATH=/app

# # Default command
# CMD ["python", "src/chatbot/api.py"]

# # Expose API port
# EXPOSE 5000