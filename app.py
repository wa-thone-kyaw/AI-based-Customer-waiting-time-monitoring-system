import os
import torch
from flask import Flask, render_template, request, redirect, url_for, Response, jsonify
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

# Login credentials
USERNAME = "admin"
PASSWORD = "password"

# Routes
@app.route("/")
def home():
    return render_template("login.html")


@app.route("/login", methods=["POST"])
def login():
    username = request.form.get("username")
    password = request.form.get("password")
    if username == USERNAME and password == PASSWORD:
        return redirect(url_for("index"))
    else:
        return redirect(url_for("home"))


@app.route("/index")
def index():
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


@app.route("/settings", methods=["GET", "POST"])
def settings():
    global setTime
    if request.method == "POST":
        data = request.json
        setTime = float(data.get("setTime", setTime))
    return jsonify({"setTime": setTime})


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


# YOLOv8 model loading
model = YOLO("yolov8l.pt")
video_path = "mmttest3.mp4"
cap = cv2.VideoCapture(video_path)

# Data structures
detected_people = {}
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
setTime = 10

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
            if "orders" in person_info:
                person_info["time"] += current_time - person_info["last_update_time"]
                person_info["last_update_time"] = current_time
        socketio.emit("update_waiting_times", get_waiting_times())
        time.sleep(1)


def get_waiting_times():
    waiting_times = {}
    current_time = time.time()
    for person_info in detected_people.values():
        if "orders" in person_info:
            elapsed_time = current_time - person_info["time"]
            order_elapsed_time = current_time - person_info.get("order_start_time", current_time)

            # Format time as minutes:seconds
            waiting_time_str = time.strftime("%M:%S", time.gmtime(elapsed_time))
            order_waiting_time_str = time.strftime("%M:%S", time.gmtime(order_elapsed_time))

            if elapsed_time > setTime:
                waiting_time_str += " (EXCEEDED)"
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
                "orders": orders_str,
            }
    return waiting_times


update_thread = threading.Thread(target=update_waiting_times)
update_thread.daemon = True
update_thread.start()


def detect_people():
    global person_id_counter
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        frame = cv2.resize(frame, (frame_width, frame_height))
        results = model(frame)

        for result in results:
            for box in result.boxes:
                class_id = int(box.cls.item())
                confidence = box.conf.item()
                if confidence > 0.5 and class_id == 0:
                    x1, y1, x2, y2 = map(int, box.xyxy[0].cpu().numpy())
                    centroid = (x1 + x2) // 2, (y1 + y2) // 2

                    matched_person_id = None
                    for person_id, person_info in detected_people.items():
                        last_centroid = person_info["centroid"]
                        distance = np.linalg.norm(
                            np.array(centroid) - np.array(last_centroid)
                        )
                        if distance < 50:
                            matched_person_id = person_id
                            break

                    if matched_person_id is None:
                        detected_people[person_id_counter] = {
                            "id": person_id_counter,
                            "centroid": centroid,
                            "bbox": (x1, y1, x2 - x1, y2 - y1),
                            "time": time.time(),
                            "last_update_time": time.time(),
                            "alarm_triggered": False,
                            "orders": [],
                        }
                        colors_dict[person_id_counter] = strong_colors[
                            person_id_counter % len(strong_colors)
                        ]
                        person_id_counter += 1
                    else:
                        detected_people[matched_person_id].update(
                            {
                                "centroid": centroid,
                                "bbox": (x1, y1, x2 - x1, y2 - y1),
                                "last_update_time": time.time(),
                                "alarm_triggered": False,
                            }
                        )

        for person_info in detected_people.values():
            if "orders" in person_info:
                elapsed_time = time.time() - person_info["time"]
                waiting_time_str = time.strftime("%M:%S", time.gmtime(elapsed_time))
                order_elapsed_time = time.time() - person_info.get(
                    "order_start_time", time.time()
                )
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
        yield (b"--frame\r\n" b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n")


if __name__ == "__main__":
    socketio.run(app, debug=True)
