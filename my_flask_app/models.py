import json
import os
from datetime import datetime

DATA_FILE = 'data.json'
CLOCKED_IN_FILE = 'clocked_in.json'
LOG_FILE = 'logs.json'
EMPLOYEES_FILE = 'employees.json'

def load_data(file, default=None):
    if os.path.exists(file):
        with open(file, 'r') as f:
            return json.load(f)
    return default if default is not None else {}

def save_data(data, file):
    with open(file, 'w') as f:
        json.dump(data, f, indent=4)

def reset_weekly_data():
    data = load_data(DATA_FILE, {})
    for employee in data.keys():
        data[employee]['weekday'] = 0
        data[employee]['weekend'] = 0
        data[employee]['public_holidays'] = 0
        data[employee]['deliveries'] = 0
    save_data(data, DATA_FILE)

def add_hours(employee, hours, deliveries):
    data = load_data(DATA_FILE, {})
    if employee not in data:
        data[employee] = {'weekday': 0, 'weekend': 0, 'public_holidays': 0, 'deliveries': 0}
    day = datetime.now().weekday()
    if day < 5:
        data[employee]['weekday'] += hours
    else:
        data[employee]['weekend'] += hours
    data[employee]['deliveries'] += deliveries
    save_data(data, DATA_FILE)

def clock_in(employee):
    clocked_in_data = load_data(CLOCKED_IN_FILE, {})
    log_data = load_data(LOG_FILE, {})
    current_time = datetime.now().isoformat()
    formatted_time = datetime.now().strftime("%Y-%m-%d %H:%M")
    clocked_in_data[employee] = {'time': current_time}

    if employee not in log_data:
        log_data[employee] = []

    log_data[employee].append({
        'login_time': formatted_time,
        'logout_time': '',
        'deliveries': 0,
        'is_public_holiday': datetime.now().weekday() >= 5,
        'login_timestamp': current_time,
        'logout_timestamp': ''
    })
    save_data(clocked_in_data, CLOCKED_IN_FILE)
    save_data(log_data, LOG_FILE)

def clock_out(employee, deliveries):
    clocked_in_data = load_data(CLOCKED_IN_FILE, {})
    log_data = load_data(LOG_FILE, {})
    if employee in clocked_in_data:
        clock_in_time = datetime.fromisoformat(clocked_in_data.pop(employee)['time'])
        hours_worked = (datetime.now() - clock_in_time).total_seconds() / 3600
        formatted_time = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        for log in log_data[employee]:
            if log['logout_time'] == '':
                log['logout_time'] = formatted_time
                log['hours_worked'] = hours_worked
                log['deliveries'] = deliveries
                log['logout_timestamp'] = datetime.now().isoformat()
                break

        add_hours(employee, hours_worked, deliveries)
        save_data(clocked_in_data, CLOCKED_IN_FILE)
        save_data(log_data, LOG_FILE)
        return hours_worked
    return 0

def get_clocked_in_employees():
    return load_data(CLOCKED_IN_FILE, {})

def get_summary():
    return load_data(DATA_FILE, {})

def get_logs():
    logs = load_data(LOG_FILE, {})
    all_logs = []
    for employee, logs_list in logs.items():
        for log in logs_list:
            all_logs.append((employee, log))
    sorted_logs = sorted(all_logs, key=lambda x: x[1]['logout_timestamp'])
    return sorted_logs

def get_employees():
    return load_data(EMPLOYEES_FILE, [])

def add_employee(employee_name):
    employees = load_data(EMPLOYEES_FILE, [])
    if employee_name not in employees:
        employees.append(employee_name)
    save_data(employees, EMPLOYEES_FILE)
