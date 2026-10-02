import os
from datetime import datetime
from flask import current_app
from .models import db


def backup_database():
    """
    Minimalist backup approach for SQLite.
    For Postgres on Railway you'd dump with pg_dump via subprocess.
    """
    uri = current_app.config["SQLALCHEMY_DATABASE_URI"]
    if uri.startswith("sqlite:///"):
        path = uri.replace("sqlite:///", "")
        if os.path.exists(path):
            backup_dir = os.path.join(os.path.dirname(path), "backups")
            os.makedirs(backup_dir, exist_ok=True)
            timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
            backup_path = os.path.join(backup_dir, f"backup_{timestamp}.db")
            with open(path, "rb") as src, open(backup_path, "wb") as dst:
                dst.write(src.read())
            print(f"Database backup: {backup_path}")
    else:
        # For Postgres on Railway you'd do something like:
        # os.system(f"pg_dump {uri} > backup_{timestamp}.sql")
        print("Implement Postgres backup logic here.")
