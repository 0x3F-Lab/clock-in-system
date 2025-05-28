# Use Python image
FROM python:3.13-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update

# Upgrade pip, setuptools, and wheel to the latest versions
RUN pip install --upgrade pip setuptools wheel

# Copy project files
COPY . .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose Django's development server port
EXPOSE 8000

# Add entrypoint script
RUN chmod +x entrypoint.sh

# Run entrypoint script
ENTRYPOINT ["sh", "entrypoint.sh"]

# Command to run the server
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]