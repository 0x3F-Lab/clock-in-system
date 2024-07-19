from flask import Blueprint, render_template, request, redirect, url_for
from models import People, Stores, Logs
from datetime import datetime
import pytz

employee_bp = Blueprint('employee', __name__)

# Define your local timezone
local_tz = pytz.timezone('Australia/Perth')

@employee_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        view = request.form.get('view')
        if view == 'employee':
            return redirect(url_for('employee.employee_view'))
        elif view == 'manager':
            return redirect(url_for('employee.manager'))
    return render_template('login.html')

@employee_bp.route('/employee', methods=['GET', 'POST'])
def employee_view():
    if request.method == 'POST':
        action = request.form.get('action')
        employee_name = request.form.get('employee')
        deliveries = request.form.get('deliveries', '0')
        
        try:
            deliveries = int(deliveries)
        except ValueError:
            deliveries = 0

        employee = People.query.filter_by(name=employee_name).first()
        if employee:
            employee.clock_in_out(deliveries=deliveries)
        
        return redirect(url_for('employee.employee_view'))

    employees = People.query.all()
    clocked_in_employees = People.query.filter_by(clocked_in=True).all()
    return render_template('employee.html', employees=employees, clocked_in_employees=clocked_in_employees)

@employee_bp.route('/manager')
def manager():
    summary = get_summary()
    logs = get_logs()
    # Convert times to local timezone for display
    for log in logs:
        if log.login_time:
            log.login_time = log.login_time.astimezone(local_tz)
        if log.logout_time:
            log.logout_time = log.logout_time.astimezone(local_tz)
    return render_template('manager.html', summary=summary, logs=logs)

@employee_bp.route('/add_employee', methods=['POST'])
def add_employee_view():
    employee_name = request.form.get('new_employee')
    add_employee(employee_name)
    return redirect(url_for('employee.manager'))
