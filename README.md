# Clock-In System

This is a Django-based web application for managing employee clock-in and clock-out with a simple authentication system for managers and employees.

---

## Features

* **Login**: Separate login options for managers (unique password) and employees (shop-wide passcode).
* **Manager Dashboard**: Managers can view employee data and access management features.
* **Employee Clock-In**: Employees can clock in and clock out easily.

---

## Prerequisites

* Python 3.10 or higher
* Django 3.2 or higher

---

## Setting Up the Project

### 1. Clone the repository

```bash
git clone git@github.com:0x3F-Lab/clock-in-system.git
cd clock-in-system
```

### 2. Duplicate the environment file

```bash
cp src/.env.development src/.env
```

**NOTE:** Please modify the database password in the `.env` file.

### 3. Start the containers

```bash
cd src
docker-compose up --build
```

The site is hosted at `http://localhost:8000` while the database is available at `localhost:5432`.

**NOTE:** This will automatically apply all migrations to the database on startup.

### 4. (Optional) Set up a virtual environment

This is not strictly required, but it is useful for running local management commands or tests.

```bash
python -m venv venv
source ./venv/bin/activate
pip install -r ./src/django/requirements.txt
```

### 5. Set up pre-commit hooks (for development)

This ensures linting is run before pushes, helping maintain code consistency.

```bash
pip install black pre-commit
pre-commit install  # Run in the root directory
```

---

## Accessing the Django Admin Page

This page makes accessing and editing database entries significantly easier, as it integrates with your connected models.

First, ensure the `Django` container is running:

```bash
docker exec -it Django bash
```

Then create a superuser:

```bash
cd /app
python manage.py createsuperuser
exit
```

Visit `http://localhost:8000/admin-panel/` and log in using the newly created account.

---

## Seeding the Database

To populate the system with a demo store, manager, and five employees:

```bash
cd src/django
python manage.py seed_dev_data
```

If you would like a clean slate before reseeding, flush the database:

```bash
python manage.py flush --no-input
```

---

## Testing

It is recommended to install the requirements in a virtual environment.

```bash
python -m venv venv
source ./venv/bin/activate
pip install -r ./src/django/requirements.txt
```

Tests will use an in-memory SQLite3 database, isolating them from the main database.

```bash
cd ./src/django
pytest
```

---

## Updating Requirements

Create a virtual environment to keep project requirements separate from your system Python packages.

```bash
python -m venv venv
source ./venv/bin/activate
```

Install existing requirements:

```bash
pip install -r ./src/django/requirements.txt
```

Add or update any extra packages, then freeze the current requirements:

```bash
pip freeze > ./src/django/requirements.txt
```

**NOTE:** Ensure the compose containers are **rebuilt** to include any new packages.