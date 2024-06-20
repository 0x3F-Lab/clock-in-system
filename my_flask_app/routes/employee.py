from flask import Blueprint, render_template

employee_bp = Blueprint('employee', __name__)

@employee_bp.route('/clock_in')
def clock_in():
    return render_template('clock_in.html')

@employee_bp.route('/clock_out')
def clock_out():
    return render_template('clock_out.html')
