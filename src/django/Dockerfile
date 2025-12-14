# Use Python image
FROM python:3.13-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update

# Upgrade pip, setuptools, and wheel to the latest versions
RUN pip install --upgrade pip setuptools wheel

# Create user and group
RUN groupadd -r django && useradd -r -g django django

# Copy project files
COPY . .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Ensure correct ownership
RUN chown -R django:django /app

# Expose Django's development server port
EXPOSE 8000

# Set user
USER django

# Add entrypoint script
RUN chmod +x entrypoint.sh

# Run entrypoint script
ENTRYPOINT ["sh", "entrypoint.sh"]

# Command to run the server -- inject support for vscode debugger
CMD ["python", "-Xfrozen_modules=off", "-m", "debugpy", "--listen", "0.0.0.0:5678", "manage.py", "runserver", "0.0.0.0:8000"]
