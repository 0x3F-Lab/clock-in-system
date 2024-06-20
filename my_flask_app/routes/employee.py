from flask import Blueprint, render_template, redirect, url_for, request

employee_bp = Blueprint('employee', __name__)

@employee_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        return redirect(url_for('employee.clock_in'))
    return render_template('login.html')

@employee_bp.route('/clock_in', methods=['GET', 'POST'])
def clock_in():
    if request.method == 'POST':
        return redirect(url_for('employee.clock_out'))
    return render_template('clock_in.html')

@employee_bp.route('/clock_out', methods=['GET', 'POST'])
def clock_out():
    return render_template('clock_out.html')
