from flask import Flask, request, jsonify
from dapr.clients import DaprClient
from kafka import KafkaProducer
import json
import os
import psycopg2
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

# Kafka producer
producer = KafkaProducer(
    bootstrap_servers=os.getenv("KAFKA_BROKERS", "kafka:9092"),
    value_serializer=lambda v: json.dumps(v).encode("utf-8")
)

# Dapr client
dapr_client = DaprClient()

@app.route("/register", methods=["POST"])
def register_user():
    data = request.get_json()
    user_id = data.get("user_id")
    name = data.get("name")
    email = data.get("email")
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO users (user_id, name, email) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
            (user_id, name, email)
        )
        conn.commit()
    
    return jsonify({"message": "User registered", "user_id": user_id}), 201

@app.route("/book_ride", methods=["POST"])
def book_ride():
    data = request.get_json()
    user_id = data.get("user_id")
    pickup = data.get("pickup_location")
    dropoff = data.get("dropoff_location")
    
    ride_id = f"ride_{user_id}_{int(time.time())}"
    
    # Save ride state with Dapr
    with dapr_client:
        dapr_client.save_state(
            store_name="statestore",
            key=ride_id,
            value=json.dumps({"ride_id": ride_id, "user_id": user_id, "status": "pending", "pickup": pickup, "dropoff": dropoff})
        )
    
    # Publish ride request to Kafka
    producer.send("ride_requests", {
        "ride_id": ride_id,
        "user_id": user_id,
        "pickup": pickup,
        "dropoff": dropoff
    })
    
    return jsonify({"message": "Ride booked", "ride_id": ride_id}), 202

@app.route("/ride_status/<ride_id>", methods=["GET"])
def ride_status(ride_id):
    with dapr_client:
        state = dapr_client.get_state(store_name="statestore", key=ride_id)
        if state.data:
            return jsonify(json.loads(state.data)), 200
        return jsonify({"message": "Ride not found"}), 404

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)