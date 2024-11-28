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
    **NOTE:** This will automatically apply all migrations to the database on all startups.

4. **Setting up pre-commit (Developing)**
   
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

The tests conducted will use a dummy database as a substitute for the Postgres database. Specifically, it will use an in-memory SQLite3 database.

```bash
cd src/django
python manage.py test -v 2
```
