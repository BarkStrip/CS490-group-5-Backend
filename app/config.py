import os

# Use environment variable if set (good for deployment)
url = os.environ.get('MYSQL_PUBLIC_URL')

if not url:
    raise ValueError("MYSQL_PUBLIC_URL environment variable is required")

if url and not url.startswith('mysql+pymysql://'):
    url = url.replace('mysql://', 'mysql+pymysql://', 1)

class Config:
    SQLALCHEMY_DATABASE_URI = url
    SQLALCHEMY_TRACK_MODIFICATIONS = False
