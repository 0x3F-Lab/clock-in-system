from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime, timezone
import pytz # used to get time in perth 

db = SQLAlchemy()


local_tz = pytz.timezone('Australia/Perth')

class People(db.Model, UserMixin):
    person_id = db.Column(db.Integer, primary_key=True, nullable=False)
    store_id = db.Column(db.Integer, db.ForeignKey('stores.store_id'), nullable=False, index=True)
    name = db.Column(db.String(128), nullable=False, index=True) # Index by name for easier lookup (names can be the same)
    clocked_in = db.Column(db.Boolean, default=False, nullable=False, index=True)
    weekday_hours = db.Column(db.Float, default=0, nullable=False)
    weekend_hours = db.Column(db.Float, default=0, nullable=False)
    public_holidays = db.Column(db.Float, default=0, nullable=False)
    deliveries = db.Column(db.Integer, default=0, nullable=False)
    creationDate = db.Column(db.DateTime, nullable=False, default=datetime.now)
    is_manager = db.Column(db.Boolean, default=False, nullable=False)

    logs = db.relationship('Logs', backref='employee', lazy='dynamic', foriegn_keys='Logs.log_id') # Link users to any logs they generate

    # Override the id function
    def get_id(self):
        return str(self.person_id)
    
    # Clock in/out with 15m protection window (prevents double clocking)
    def clock_in_out(self, deliveries=0):
        current_time_local = datetime.now(local_tz)
        if self.clocked_in:
            # Clocking out
            log = Logs.query.filter_by(employee_id=self.person_id, logout_time=None).first()
            if log and (current_time_local - log.login_time).total_seconds() >= 15 * 60:  # 15m protection window
                clock_in_time = log.login_time
                if clock_in_time.tzinfo is None:
                    clock_in_time = local_tz.localize(clock_in_time)
                hours_worked = (current_time_local - clock_in_time).total_seconds() / 3600
                log.logout_time = current_time_local
                log.hours_worked = hours_worked
                log.deliveries = deliveries
                log.is_public_holiday = current_time_local.weekday() >= 5
                # Add hours to the appropriate field
                if current_time_local.weekday() < 5:
                    self.weekday_hours += hours_worked
                else:
                    self.weekend_hours += hours_worked
                self.clocked_in = False
                self.deliveries += deliveries  # Add deliveries to person's data
        else:
            # Clocking in
            last_log = Logs.query.filter_by(employee_id=self.person_id).order_by(Logs.login_time.desc()).first()
            if last_log is None or (current_time_local - last_log.logout_time).total_seconds() >= 15 * 60:  # 15m protection window
                self.clocked_in = True
                log = Logs(employee_id=self.person_id, login_time=current_time_local)
                db.session.add(log)
        db.session.commit()
        

class Stores(db.Model):
    store_id = db.Column(db.Integer, primary_key=True, nullable=False)
    store_name = db.Column(db.string(128), nullable=False, index=True)

    def get_id(self):
        return str(self.store_id)
    
    def count_employees(self):
        return People.query.filter_by(store_id=self.store_id).count()

    def count_managers(self):
        return People.query.filter_by(store_id=self.store_id, is_manager=True).count()
    
    def get_clocked_in_employees(self):
        return People.query.filter_by(store_id=self.store_id, clocked_in=True).all()

    def get_logs(self):
        return Logs.query.join(People).filter(People.store_id == self.store_id).order_by(Logs.logout_time.desc()).all()

    def get_employees(self):
        return People.query.filter_by(store_id=self.store_id).all()

    def add_employee(self, employee_name):
        employee = People(name=employee_name, store_id=self.store_id)
        db.session.add(employee)
        db.session.commit()

    def reset_weekly_data(self):
        employees = People.query.filter_by(store_id=self.store_id).all()
        for employee in employees:
            employee.weekday_hours = 0
            employee.weekend_hours = 0
            employee.public_holidays = 0
            employee.deliveries = 0
        db.session.commit()

class Logs(db.Model):
    log_id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('people.user_id'), nullable=False)
    login_time = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    logout_time = db.Column(db.DateTime(timezone=True))
    hours_worked = db.Column(db.Float)
    deliveries = db.Column(db.Integer)
    is_public_holiday = db.Column(db.Boolean)

    def get_id(self):
        return str(self.log_id)


# def reset_weekly_data():
#     for employee in People.query.all():
#         employee.weekday_hours = 0
#         employee.weekend_hours = 0
#         employee.public_holidays = 0
#         employee.deliveries = 0
#     db.session.commit()
#
# def add_hours(employee, hours, deliveries):
#     current_time_local = datetime.now(local_tz)
#     day = current_time_local.weekday()
#     if day < 5:
#         employee.weekday_hours += hours
#     else:
#         employee.weekend_hours += hours
#     employee.deliveries += deliveries
#     db.session.commit()

# def clock_in(employee_name):
#     employee = People.query.filter_by(name=employee_name).first()
#     if employee:
#         employee.clocked_in = True
#         log = Logs(employee_id=employee.id, login_time=datetime.now(local_tz))
#         db.session.add(log)
#         db.session.commit()

# def clock_out(employee_name, deliveries):
#     employee = People.query.filter_by(name=employee_name).first()
#     if employee and employee.clocked_in:
#         log = Logs.query.filter_by(employee_id=employee.id, logout_time=None).first()
#         if log:
#             clock_in_time = log.login_time
#             if clock_in_time.tzinfo is None:
#                 clock_in_time = local_tz.localize(clock_in_time)
#             current_time_local = datetime.now(local_tz)
#             hours_worked = (current_time_local - clock_in_time).total_seconds() / 3600
#             log.logout_time = current_time_local
#             log.hours_worked = hours_worked
#             log.deliveries = deliveries
#             log.is_public_holiday = current_time_local.weekday() >= 5
#             add_hours(employee, hours_worked, deliveries)
#             employee.clocked_in = False
#             db.session.commit()
#             return hours_worked
#     return 0

# def get_clocked_in_employees():
#     return People.query.filter_by(clocked_in=True).all()

# def get_summary():
#     return People.query.all()

# def get_logs():
#     return Logs.query.order_by(Logs.logout_time.desc()).all()

# def get_employees():
#     return People.query.all()

# def add_employee(employee_name):
#     employee = People(name=employee_name)
#     db.session.add(employee)
#     db.session.commit()
