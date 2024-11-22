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

2. **Duplicate env for use**:
  ```bash
  cp src/.env.example src/.env
  ```
  ### **NOTE:** Please modify the database password in the `.env` file!

3. **Start the containers**:
  ```bash
  cd src
  docker-compose up --build
  ```

  ### **NOTE:** This will automatically apply all migrations to the database on all startups.


