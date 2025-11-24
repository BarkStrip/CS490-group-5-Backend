import os
from sqlalchemy import text
from app.extensions import db
from main import create_app

app = create_app()

# Path to the SQL file
sql_path = os.path.join(os.path.dirname(__file__), "NEW_SQL_script.sql")

with app.app_context():
    with open(sql_path) as f:
        sql_commands = f.read()
        db.session.execute(text(sql_commands))  # wrap in text()
        db.session.commit()

print("SQL script executed successfully!")
