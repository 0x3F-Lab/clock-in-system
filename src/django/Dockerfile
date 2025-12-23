# Use Python image
FROM python:3.13-slim

# Build arguments for UID/GID
ARG UID=1000
ARG GID=1000

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update \
  && apt-get install -y --no-install-recommends build-essential \
  && rm -rf /var/lib/apt/lists/*

# Upgrade pip, setuptools, and wheel to the latest versions
RUN pip install --upgrade pip setuptools wheel

# Create group and user with explicit UID/GID
RUN groupadd -g ${GID} django \
  && useradd -u ${UID} -g ${GID} -m django

# Copy project files
COPY . .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Create logs directory to prevent logging crash during collectstatic
RUN mkdir -p /app/logs

# Ensure correct ownership
RUN chown -R ${UID}:${GID} /app

# Add entrypoint script
RUN chmod +x entrypoint.sh

# Set user
USER django

# Expose Django's development server port
EXPOSE 8000 5678

# Run entrypoint script
ENTRYPOINT ["sh", "entrypoint.sh"]

# Command to run the server -- inject support for vscode debugger
CMD ["python", "-Xfrozen_modules=off", "-m", "debugpy", "--listen", "0.0.0.0:5678", "manage.py", "runserver", "0.0.0.0:8000"]
