from flask import Flask, request, jsonify
from dapr.clients import DaprClient
from kafka import KafkaConsumer
import json
import os
import psycopg2
from contextlib import contextmanager
import threading

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

# Dapr client
dapr_client = DaprClient()

# Kafka consumer for ride requests
def consume_ride_requests():
    consumer = KafkaConsumer(
        "ride_requests",
        bootstrap_servers=os.getenv("KAFKA_BROKERS", "kafka:9092"),
        value_deserializer=lambda x: json.loads(x.decode("utf-8"))
    )
    for message in consumer:
        ride = message.value
        ride_id = ride["ride_id"]
        # Simulate driver assignment
        with dapr_client:
            dapr_client.save_state(
                store_name="statestore",
                key=ride_id,
                value=json.dumps({**ride, "status": "assigned", "driver_id": "driver_1"})
            )

@app.route("/register_driver", methods=["POST"])
def register_driver():
    data = request.get_json()
    driver_id = data.get("driver_id")
    name = data.get("name")
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO drivers (driver_id, name) VALUES (%s, %s) ON CONFLICT DO NOTHING",
            (driver_id, name)
        )
        conn.commit()
    
    return jsonify({"message": "Driver registered", "driver_id": driver_id}), 201

@app.route("/update_location", methods=["POST"])
def update_location():
    data = request.get_json()
    driver_id = data.get("driver_id")
    location = data.get("location")
    
    # Save driver location with Dapr
    with dapr_client:
        dapr_client.save_state(
            store_name="statestore",
            key=f"driver_{driver_id}_location",
            value=json.dumps({"driver_id": driver_id, "location": location})
        )
    
    return jsonify({"message": "Location updated"}), 200

if __name__ == "__main__":
    # Start Kafka consumer in a separate thread
    threading.Thread(target=consume_ride_requests, daemon=True).start()
    app.run(host="0.0.0.0", port=5002)