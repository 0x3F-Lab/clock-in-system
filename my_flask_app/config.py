import os

class Config:
    SECRET_KEY = 'your_secret_key'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///clock_in_system.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
