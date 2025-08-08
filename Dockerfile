# Use Python 3.11 slim for smaller image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code (in production)
# In development, we'll use bind mounts instead
COPY . .

# Expose port if needed (LiveKit agents don't typically need ports)
# EXPOSE 3001

# Default command (can be overridden in docker-compose)
CMD ["python", "basic_agent.py", "dev"]