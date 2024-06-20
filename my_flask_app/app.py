from flask import Flask, redirect, url_for
from routes.employee import employee_bp

app = Flask(__name__)

# Register Blueprints
app.register_blueprint(employee_bp, url_prefix='/employee')

@app.route('/')
def index():
    return redirect(url_for('employee.login'))

if __name__ == '__main__':
    app.run(debug=True)
