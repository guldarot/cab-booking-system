from flask import Flask, render_template
from dapr.clients import DaprClient
import psycopg2
import os
from contextlib import contextmanager

app = Flask(__name__)

# Database connection
DB_HOST = os.getenv("DB_HOST", "postgres")
DB_NAME = os.getenv("DB_NAME", "cab_booking")
DB_USER = os.getenv("DB_USER", "user")
DB_PASS = os.getenv("DB_PASS", "password")

@contextmanager
def get_db_connection():
    conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASS)
    try:
        yield conn
    finally:
        conn.close()

@app.route("/")
def dashboard():
    # Fetch users
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, name, email FROM users")
        users = cursor.fetchall()
    
    # Fetch drivers
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT driver_id, name FROM drivers")
        drivers = cursor.fetchall()
    
    # Fetch ride states from Dapr
    rides = []
    with DaprClient() as dapr_client:
        # This is a simplified example; in production, use a state query or pagination
        for i in range(100):  # Arbitrary limit
            state = dapr_client.get_state(store_name="statestore", key=f"ride_{i}")
            if state.data:
                rides.append(json.loads(state.data))
    
    return render_template("index.html", users=users, drivers=drivers, rides=rides)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5003)