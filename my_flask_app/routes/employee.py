from flask import Blueprint, render_template, redirect, url_for, request
from models import add_hours, get_summary, clock_in, clock_out, get_clocked_in_employees, get_logs, get_employees, add_employee

employee_bp = Blueprint('employee', __name__)

@employee_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        view = request.form.get('view')
        if view == 'employee':
            return redirect(url_for('employee.clock'))
        elif view == 'manager':
            return redirect(url_for('employee.manager_view'))
    return render_template('login.html')

@employee_bp.route('/clock', methods=['GET', 'POST'])
def clock():
    employees = get_employees()
    clocked_in_employees = get_clocked_in_employees()
    if request.method == 'POST':
        employee = request.form.get('employee')
        action = request.form.get('action')
        deliveries = request.form.get('deliveries')
        deliveries = int(deliveries) if deliveries else 0
        if action == 'clock_in':
            clock_in(employee)
            return redirect(url_for('employee.clock'))
        elif action == 'clock_out':
            clock_out(employee, deliveries)
            return redirect(url_for('employee.clock'))
    return render_template('employee.html', employees=employees, clocked_in_employees=clocked_in_employees)

@employee_bp.route('/manager', methods=['GET', 'POST'])
def manager_view():
    if request.method == 'POST':
        new_employee = request.form.get('new_employee')
        if new_employee:
            add_employee(new_employee)
            return redirect(url_for('employee.manager_view'))
    summary_data = get_summary()
    logs_data = get_logs()
    return render_template('manager.html', summary=summary_data, logs=logs_data, employees=get_employees())
