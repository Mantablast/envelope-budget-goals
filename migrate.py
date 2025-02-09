# migrate.py
from app import app, db
from sqlalchemy import text

# Ensure the application context is pushed
with app.app_context():
    # Add the new column to the existing table
    with db.engine.connect() as connection:
        connection.execute(text('ALTER TABLE goal ADD COLUMN income_per_pay_day FLOAT NOT NULL DEFAULT 0'))