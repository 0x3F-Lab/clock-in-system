from flask import Flask, render_template
from routes.employee import employee_bp

app = Flask(__name__)

app.register_blueprint(employee_bp, url_prefix='/employee')

if __name__ == '__main__':
    app.run(debug=True)
