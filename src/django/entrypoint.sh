#!/bin/sh

# Exit immediately if a command exits with a non-zero status
set -e

# Run database migrations
echo "Running database migrations..."
python manage.py makemigrations
python manage.py migrate

# Start the Django development server
echo "Starting Django server..."
exec "$@"
