# Clock-In System

This is a Django-based web application for managing employee clock-in and clock-out with a simple authentication system for managers and employees.

## Features

- **Login**: Separate login options for managers (unique password) and employees (shop-wide passcode).
- **Manager Dashboard**: Managers can view employee data and access management features.
- **Employee Clock-In**: Employees can clock in and clock out easily.

## Installation

### Prerequisites

- Python 3.10 or higher
- Django 3.2 or higher

### Setting Up the Project

1. **Clone the repository**:
   ```bash
   git clone git@github.com:0x3F-Lab/clock-in-system.git
   cd clock-in-system
   ```

2. **Duplicate env for use**:
    ```bash
    cp src/.env.example src/.env
    ```
    **NOTE:** Please modify the database password in the `.env` file!

3. **Start the containers**:
    ```bash
    cd src
    docker-compose up --build
    ```
    The site is hosted at `http://localhost:8000` while the database is located at `http://localhost:5432`.
    **NOTE:** This will automatically apply all migrations to the database on all startups.

4. **Setting up virtual environment**
    ```bash
    python -m venv venv
    source ./venv/bin/activate
    pip install -r ./src/django/requirements.txt
    ```
    This is not strictly needed, it is purely for inserting the required values into the database.

5. **Inserting the constants into the database**
    ```bash
    python ./src/setup_db.py
    ```
    Note: This can be performed using the django admin panel.

6. **Setting up pre-commit (Developing)**
   
    This will setup the linting process client side before pushes are made to the remote repo. This ensures ease of use for all users without having to re-push with updated linting.
    ```bash
    pip install black pre-commit
    pre-commit install  # Run in root directory
    ```

---

### **Accessing Django Admin Page**

This page makes accessing the database significantly easier as it directly integrates with the connected models. First, a superuser must be created for a login account.

```bash
# Ensure the `Django` container is running.
docker exec -it Django bash
```

```bash
cd /app
python manage.py createsuperuser
exit
```

Then, go to `http://localhost:8000/admin/` and use the newly created account to log in.

---

### **Testing**

For proper testing, the requirements are required to be installed, preferably with a virtual envrionemnt.

```bash
python -m venv venv
source ./venv/bin/activate
pip install -r ./src/django/requirements.txt
```

The tests conducted will use a dummy database as a substitute for the Postgres database. Specifically, it will use an in-memory SQLite3 database.

```bash
cd ./src/django
pytest
```

---

### **Updating Requirements (Packages)**

Make an environment to keep the requirements seperate from you system requirements. Ensure to do this in the project's root directory.

```bash
python -m venv venv
source ./venv/bin/activate
```

Install exisiting requirements.

```bash
pip install ./src/django/requirements.txt
```

Add any extra requirements then freeze the current requirements to update the file.
```bash
pip freeze > ./src/django/requirements.txt
```

**NOTE:** Ensure that the compose containers are __REBUILT!__ to include the new packages.