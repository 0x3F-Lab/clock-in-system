from flask import Blueprint, render_template, request, redirect, url_for, flash
from models import People, Stores, Logs, db
from flask_login import login_user, logout_user, login_required
import forms
from datetime import datetime
import pytz

employee_bp = Blueprint('employee', __name__)

# Define your local timezone
local_tz = pytz.timezone('Australia/Perth')

@employee_bp.route('/login', methods=['GET', 'POST'])
def login():
    form = forms.LoginForm()
    if form.validate_on_submit():
        login_data = form.login.data
        password = form.password.data
        remember_me = form.remember_me.data

        if '@' in login_data:
            user = People.query.filter_by(email=login_data).first()
        else:
            user = People.query.filter_by(person_id=login_data).first()

        if user and user.check_password(password):
            login_user(user, remember=remember_me)
            flash('Logged in successfully.', 'success')
            return redirect(url_for('employee.employee_view' if not user.is_manager else 'employee.manager'))

        flash('Invalid username or password.', 'danger')

    return render_template('login.html', form=form)

@employee_bp.route('/signup', methods=['GET', 'POST'])
def signup():
    form = forms.SignupForm()
    if form.validate_on_submit():
        employee_id = form.employee_id.data
        email = form.email.data
        password = form.password.data

        # SHOULD BE IN A TRY-EXCEPT BLOCK
        employee = People.query.filter_by(person_id=employee_id).first()
        if employee:
            employee.email = email
            employee.set_password(password)
            db.session.commit()
            login_user(employee, remember=False)
            flash('Account created successfully.', 'success')
            return redirect(url_for('employee.employee_view'))
        flash('Employee ID does not exist.', 'danger')

    return render_template('signup.html', form=form)

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
@login_required
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
@login_required
def add_employee_view():
    employee_name = request.form.get('new_employee')
    add_employee(employee_name)
    return redirect(url_for('employee.manager'))
