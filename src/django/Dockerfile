# Use Python image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y gcc libpq-dev

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