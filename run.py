"""Application entry point for College Classroom Scheduling System."""

import os
from app import create_app
from database.db import db
from database.seed_data import seed_database

env = os.environ.get("FLASK_ENV", "development")
app = create_app(env)

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        # Seed default database if empty
        from app.models import Department
        if not Department.query.first():
            seed_database()
            print("Database initialized and seeded with default data.")

    port = int(os.environ.get("PORT", 5000))
    host = os.environ.get("HOST", "127.0.0.1")
    print(f"College Classroom Scheduling System (MAS) - Starting server on http://{host}:{port}")
    app.run(host=host, port=port, debug=app.config.get("DEBUG", False))
