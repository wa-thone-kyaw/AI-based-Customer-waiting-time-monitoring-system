import os
import torch
from flask import Flask, render_template, request, redirect, url_for, Response, jsonify  , session
from flask_socketio import SocketIO
import cv2
import numpy as np
import time
import threading
from flask_cors import CORS
from ultralytics import YOLO

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app)
app.secret_key = 'Qf223322'
# Login credentials
USERNAME = "admin"
PASSWORD = "password"
# Home/Login Route
@app.route("/")
def home():
    if 'authenticated' in session and session['authenticated']:
        return redirect(url_for("index"))
    return render_template("login.html")
# Routes
# @app.route("/")
# def home():
#     return render_template("login.html")


# @app.route("/login", methods=["POST"])
# def login():
#     username = request.form.get("username")
#     password = request.form.get("password")
#     if username == USERNAME and password == PASSWORD:
#         return redirect(url_for("index"))
#     else:
#         return redirect(url_for("home"))
# Login Route
@app.route("/login", methods=["POST"])
def login():
    username = request.form.get("username")
    password = request.form.get("password")
    
    if username == USERNAME and password == PASSWORD:
        session['authenticated'] = True  # Store login state in session
        return redirect(url_for("index"))
    else:
        return redirect(url_for("home"))
@app.route('/logout', methods=['POST'])
def logout():
    session.clear()  # Clear the session to log out the user
    return jsonify({"message": "Logged out successfully"}), 200

# @app.route("/index")
# def index():
#     return render_template("index.html")
# Index Route (Protected)
@app.route("/index")
def index():
    if 'authenticated' not in session or not session['authenticated']:
        return redirect(url_for("home"))
    return render_template("index.html")

@app.route("/video_feed")
def video_feed():
    return Response(
        detect_people(), mimetype="multipart/x-mixed-replace; boundary=frame"
    )


@app.route("/waiting_times")
def waiting_times():
    return jsonify(get_waiting_times())


@app.route("/stop_all_alarms", methods=["POST"])
def stop_all_alarms():
    for person_info in detected_people.values():
        person_info["alarm_triggered"] = False
    return jsonify({"message": "All alarms stopped"}), 200


# @app.route("/settings", methods=["GET", "POST"])
# def settings():
#     global setTime, setOrderTime
#     if request.method == "POST":
#         data = request.json
#         setTime = float(data.get("setTime", setTime))
#         setOrderTime = float(data.get("setOrderTime", setOrderTime))
#     return jsonify({"setTime": setTime , "setOrderTime": setOrderTime})
@app.route("/settings", methods=["POST"])
def settings():
    global setTime, setOrderTime
    data = request.json
    if "setTime" in data:
        setTime = float(data.get("setTime", setTime))
        print(f"Waiting time updated to: {setTime}")
    if "setOrderTime" in data:
        setOrderTime = float(data.get("setOrderTime", setOrderTime))
        print(f"Order waiting time updated to: {setOrderTime}")
    print(f"Received settings data: {data}")
    return jsonify({"message": "Settings updated", "setTime": setTime, "setOrderTime": setOrderTime})




@app.route("/items")
def items():
    items = {
        "cakes": ["Chocolate Cake", "Vanilla Cake", "Strawberry Cake"],
        "coffee": ["Espresso", "Latte", "Cappuccino"],
    }
    return jsonify(items)


@app.route("/orders", methods=["POST"])
def orders():
    data = request.json
    person_id = int(data.get("person_id"))
    order = data.get("order")
    order_time = time.strftime("%H:%M:%S", time.localtime())  # Changed to show only time
    if person_id in detected_people:
        person_info = detected_people[person_id]
        if "orders" not in person_info:
            person_info["orders"] = []
        person_info["orders"].append({"item": order, "time": order_time})

        # Reset the order start time when an order is placed
        person_info["order_start_time"] = time.time()
        person_info["last_update_time"] = time.time()

        print(f"Order received for Person {person_id}: {order} at {order_time}")
    else:
        print(f"Person {person_id} not found.")
    return jsonify(
        {"message": "Order placed successfully", "person_id": person_id, "order": order}
    )
@app.route("/delete_order", methods=["DELETE"])
def delete_order():
    data = request.json
    person_id = int(data.get("person_id"))

    if person_id in detected_people:
        person_info = detected_people[person_id]
        
        if "orders" in person_info and person_info["orders"]:
            # Clear all orders for the person
            person_info["orders"] = []
            person_info["order_start_time"] = None  # Reset order waiting time only
            person_info["last_update_time"] = time.time()  # Update last time for tracking

            return jsonify({"message": "All orders deleted successfully."}), 200
        else:
            return jsonify({"message": "No orders found for this person."}), 404
    return jsonify({"message": "Person not found."}), 404


# Initialize video writer for output
output_filename = "Ai_based_customer_waiting_time_monitoring_system_output.mp4"

fps = 20  # Set the desired FPS
frame_width, frame_height = 640, 480  # Make sure this matches your video input resolution
video_writer = cv2.VideoWriter(
    output_filename,
    cv2.VideoWriter_fourcc(*"XVID"),  # Try XVID codec
    fps,
    (frame_width, frame_height),
)

# YOLOv8 model loading
model = YOLO("yolov8n.pt")
video_path = "S1.mp4"
cap = cv2.VideoCapture(video_path)

# Data structures
detected_people = {
    
}
person_id_counter = 1
colors_dict = {}

# Predefined colors
strong_colors = [
    (255, 0, 0),
    (0, 255, 0),
    (0, 0, 255),
    (255, 255, 0),
    (255, 0, 255),
    (0, 255, 255),
    (128, 0, 128),
    (0, 128, 128),
    (128, 128, 0),
    (255, 165, 0),
]

# Frame resizing
frame_width = 640
frame_height = 480
setTime = 20
setOrderTime = 15 
# Alarm handling
alarm_file = "alarm.wav"
alarm_sound = None

if os.path.isfile(alarm_file):
    import pygame

    pygame.init()
    alarm_sound = pygame.mixer.Sound(alarm_file)
else:
    print(f"Warning: File '{alarm_file}' not found. Alarm functionality is disabled.")


def update_waiting_times():
    while True:
        current_time = time.time()
        for person_info in detected_people.values():
            # Update total waiting time regardless of orders
            person_info["time"] += current_time - person_info["last_update_time"]
            person_info["last_update_time"] = current_time
            
            # Only update order waiting time if an order exists
            if "order_start_time" in person_info and person_info["order_start_time"] is not None:
                order_elapsed_time = current_time - person_info["order_start_time"]
                person_info["order_elapsed_time"] = order_elapsed_time  # Optional: Track separately if needed

        socketio.emit("update_waiting_times", get_waiting_times())
        time.sleep(1)
def get_waiting_times():
    waiting_times = {}
    current_time = time.time()
    for person_info in detected_people.values():
        elapsed_time = current_time - person_info["time"]
        order_elapsed_time = (
            current_time - person_info["order_start_time"]
            if person_info.get("order_start_time") is not None
            else 0
        )

        # Format time as minutes:seconds
        waiting_time_str = time.strftime("%M:%S", time.gmtime(elapsed_time))
        order_waiting_time_str = time.strftime("%M:%S", time.gmtime(order_elapsed_time))
        if elapsed_time > setTime:
                waiting_time_str += " (EXCEEDED)"
                if alarm_sound:
                    if not person_info["alarm_triggered"]:
                        alarm_sound.play()
                        person_info["alarm_triggered"] = True
        if order_elapsed_time > setOrderTime:
                order_waiting_time_str += " (EXCEEDED)"
                if alarm_sound:
                    if not person_info["alarm_triggered"]:
                        alarm_sound.play()
                        person_info["alarm_triggered"] = True
        orders_str = ", ".join(
                [f"{order['item']} ({order['time']})" for order in person_info.get("orders", [])]
            )
        waiting_times[f"Person {person_info['id']}"] = {
            "waiting_time": waiting_time_str,
            "order_waiting_time": order_waiting_time_str,
            "orders": ", ".join(
                [f"{order['item']} ({order['time']})" for order in person_info.get("orders", [])]
            ),
        }
    return waiting_times



update_thread = threading.Thread(target=update_waiting_times)
update_thread.daemon = True
update_thread.start()


def detect_people():
    global person_id_counter
    grace_period = 100000  # Allow 5 seconds before considering someone as permanently gone
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        frame = cv2.resize(frame, (frame_width, frame_height))
        results = model(frame)

        current_time = time.time()

        # Remove people who have been gone for longer than the grace period
        to_remove = []
        for person_id, person_info in detected_people.items():
            if current_time - person_info["last_seen_time"] > grace_period:
                to_remove.append(person_id)

        for person_id in to_remove:
            del detected_people[person_id]

        # Process detection results
        for result in results:
            for box in result.boxes:
                class_id = int(box.cls.item())
                confidence = box.conf.item()
                if confidence > 0.5 and class_id == 0:  # Check if it's a person
                    x1, y1, x2, y2 = map(int, box.xyxy[0].cpu().numpy())
                    centroid = (x1 + x2) // 2, (y1 + y2) // 2

                    matched_person_id = None
                    # Try to match with an existing person
                    for person_id, person_info in detected_people.items():
                        last_centroid = person_info["centroid"]
                        distance = np.linalg.norm(
                            np.array(centroid) - np.array(last_centroid)
                        )
                        if distance < 50:  # Adjust distance threshold as needed
                            matched_person_id = person_id
                            break

                    if matched_person_id is None:
                        # New person detected
                        detected_people[person_id_counter] = {
                            "id": person_id_counter,
                            "centroid": centroid,
                            "bbox": (x1, y1, x2 - x1, y2 - y1),
                            "time": time.time(),
                            "last_update_time": time.time(),
                            "last_seen_time": time.time(),  # Track last seen time
                            "alarm_triggered": False,
                            "orders": [],
                        }
                        colors_dict[person_id_counter] = strong_colors[
                            person_id_counter % len(strong_colors)
                        ]
                        person_id_counter += 1
                    else:
                        # Update existing person's info
                        detected_people[matched_person_id].update(
                            {
                                "centroid": centroid,
                                "bbox": (x1, y1, x2 - x1, y2 - y1),
                                "last_update_time": time.time(),
                                "last_seen_time": time.time(),  # Update last seen time
                                "alarm_triggered": False,
                            }
                        )

        # Drawing detected people on the frame
        for person_info in detected_people.values():
            if "orders" in person_info:
                elapsed_time = time.time() - person_info["time"]
                waiting_time_str = time.strftime("%M:%S", time.gmtime(elapsed_time))
                """ order_elapsed_time = time.time() - person_info.get(
                    "order_start_time", time.time()
                ) """
                if person_info.get("order_start_time") is not None:
                    order_elapsed_time= time.time() - person_info["order_start_time"]
                else:
                    order_elapsed_time=0    
                order_waiting_time_str = time.strftime(
                    "%M:%S", time.gmtime(order_elapsed_time)
                )
                x, y, w, h = person_info["bbox"]
                cv2.putText(
                    frame,
                    f'Person {person_info["id"]} - Waiting Time: {waiting_time_str} - Order Waiting Time: {order_waiting_time_str}',
                    (x, y - 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    colors_dict[person_info["id"]],
                    2,
                )
                cv2.circle(
                    frame,
                    person_info["centroid"],
                    5,
                    colors_dict[person_info["id"]],
                    -1,
                )

        ret, buffer = cv2.imencode(".jpg", frame)
        frame = buffer.tobytes()

        yield b"--frame\r\n" b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"


if __name__ == "__main__":
    socketio.run(app, debug=True)
