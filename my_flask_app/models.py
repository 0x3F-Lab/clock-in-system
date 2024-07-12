from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timezone
import pytz # used to get time in perth 

db = SQLAlchemy()


local_tz = pytz.timezone('Australia/Perth')

class Employee(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    clocked_in = db.Column(db.Boolean, default=False)
    logs = db.relationship('Log', backref='employee', lazy=True)
    weekday_hours = db.Column(db.Float, default=0)
    weekend_hours = db.Column(db.Float, default=0)
    public_holidays = db.Column(db.Float, default=0)
    deliveries = db.Column(db.Integer, default=0)

class Log(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employee.id'), nullable=False)
    login_time = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    logout_time = db.Column(db.DateTime(timezone=True))
    hours_worked = db.Column(db.Float)
    deliveries = db.Column(db.Integer)
    is_public_holiday = db.Column(db.Boolean)


def reset_weekly_data():
    for employee in Employee.query.all():
        employee.weekday_hours = 0
        employee.weekend_hours = 0
        employee.public_holidays = 0
        employee.deliveries = 0
    db.session.commit()

def add_hours(employee, hours, deliveries):
    current_time_local = datetime.now(local_tz)
    day = current_time_local.weekday()
    if day < 5:
        employee.weekday_hours += hours
    else:
        employee.weekend_hours += hours
    employee.deliveries += deliveries
    db.session.commit()

def clock_in(employee_name):
    employee = Employee.query.filter_by(name=employee_name).first()
    if employee:
        employee.clocked_in = True
        log = Log(employee_id=employee.id, login_time=datetime.now(local_tz))
        db.session.add(log)
        db.session.commit()

def clock_out(employee_name, deliveries):
    employee = Employee.query.filter_by(name=employee_name).first()
    if employee and employee.clocked_in:
        log = Log.query.filter_by(employee_id=employee.id, logout_time=None).first()
        if log:
            clock_in_time = log.login_time
            if clock_in_time.tzinfo is None:
                clock_in_time = local_tz.localize(clock_in_time)
            current_time_local = datetime.now(local_tz)
            hours_worked = (current_time_local - clock_in_time).total_seconds() / 3600
            log.logout_time = current_time_local
            log.hours_worked = hours_worked
            log.deliveries = deliveries
            log.is_public_holiday = current_time_local.weekday() >= 5
            add_hours(employee, hours_worked, deliveries)
            employee.clocked_in = False
            db.session.commit()
            return hours_worked
    return 0

def get_clocked_in_employees():
    return Employee.query.filter_by(clocked_in=True).all()

def get_summary():
    return Employee.query.all()

def get_logs():
    return Log.query.order_by(Log.logout_time.desc()).all()

def get_employees():
    return Employee.query.all()

def add_employee(employee_name):
    employee = Employee(name=employee_name)
    db.session.add(employee)
    db.session.commit()
