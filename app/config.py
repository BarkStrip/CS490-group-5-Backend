import os

class Config:
    # Use environment variable if set (good for deployment)
    SQLALCHEMY_DATABASE_URI = os.environ.get('MYSQL_PUBLIC_URL')

    SQLALCHEMY_TRACK_MODIFICATIONS = False
