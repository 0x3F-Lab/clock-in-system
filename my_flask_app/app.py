from flask import Flask, redirect, url_for
from config import Config
from routes.employee import employee_bp
from models import db

app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)

with app.app_context():
    db.create_all()

# Register Blueprints
app.register_blueprint(employee_bp, url_prefix='/employee')

@app.route('/')
def index():
    return redirect(url_for('employee.login'))

if __name__ == '__main__':
    app.run(debug=True)
