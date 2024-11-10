# Clock-In System

This is a Django-based web application for managing employee clock-in and clock-out with a simple authentication system for managers and employees.

## Features

- **Login**: Separate login options for managers (unique password) and employees (shop-wide passcode).
- **Manager Dashboard**: Managers can view employee data and access management features.
- **Employee Clock-In**: Employees can clock in and clock out easily.

## Installation

### Prerequisites

- Python 3.10 or higher
- MongoDB (configured and running)
- Django 3.2 or higher

### Setting Up the Project

1. **Clone the repository**:
   ```bash
   git clone https://github.com/yourusername/clock-in-system.git
   cd clock-in-system

2. **Setup virtual python environment**:
    ```bash
    python3 -m venv venv
    source venv/bin/activate  # On Windows, use `venv\Scripts\activate`

3. **Install dependencies**:
    pip install -r requirements.txt

4. **Set up MongoDB**:

Make sure MongoDB is running. I recommend using MongoDB Compass for an easy UI setup.

1. **Create Connection**:
   - Open **MongoDB Compass** and connect to your MongoDB server (local).

2. **Create Database**:
   - In MongoDB Compass, create a new database named **`clock_in_system`**.

3. **Run Migrations**:
   - From the project directory, run:
     ```bash
     python manage.py makemigrations
     python manage.py migrate
     ```
   This will set up the initial database schema in MongoDB.

