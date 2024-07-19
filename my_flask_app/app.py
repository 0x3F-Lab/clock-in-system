from flask import Flask, redirect, url_for
from flask_login import LoginManager
from config import Config
from routes.employee import employee_bp
from models import db, People

app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)

## Login manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "employee.login"

@login_manager.user_loader
def load_user(user_id):
    return People.query.get(int(user_id))

with app.app_context():
    db.create_all()

# Register Blueprints
app.register_blueprint(employee_bp, url_prefix='/employee')

@app.route('/')
def index():
    return redirect(url_for('employee.login'))

if __name__ == '__main__':
    app.run(debug=True)
