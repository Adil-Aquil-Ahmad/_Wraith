import sys
import os
import threading
import subprocess
import time
from newsbot import *
from Chatroom import *
from flask import Flask, jsonify, render_template, request, redirect, url_for
from flask_socketio import SocketIO, join_room, emit
from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QPushButton, QLineEdit, QWidget, QHBoxLayout, QTabWidget
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile, QWebEngineSettings
from PyQt6.QtCore import QUrl
from PyQt6.QtNetwork import QNetworkProxy
from Crypto.Cipher import AES
from pymongo import MongoClient
import base64
import random
from werkzeug.utils import secure_filename
from bson import ObjectId
from bson import Binary


def print_stream(stream, prefix):
    while True:
        line = stream.readline()
        if not line:
            break
        print(f"[{prefix}] {line.strip()}")

# Initialize Flask app
app = Flask(__name__)
app.config["SECRET_KEY"] = "AdilAAhmad"
socketio = SocketIO(app, cors_allowed_origins="*")
client = MongoClient("mongodb://localhost:27017/")
db = client["forum_db"]
posts_collection = db["posts"]


# === FLASK ROUTES ===
# News Routes
@app.route('/')
def home():
    return render_template('news.html')

@app.route("/data/europe")
def europe_news():
    return jsonify(fetch_nytimes_europe())

@app.route("/data/all")
def all_news():
    return jsonify(fetch_all_nytimes_news())

@app.route("/data/africa")
def africa_news():
    return jsonify(fetch_nytimes_africa())

@app.route("/data/americas")
def americas_news():
    return jsonify(fetch_nytimes_americas())

@app.route("/data/asiapac")
def asiapac_news():
    return jsonify(fetch_nytimes_asiapac())

@app.route("/data/middleeast")
def middleeast_news():
    return jsonify(fetch_nytimes_middleast())

# Chatroom Routes
chatrooms = {}

@socketio.on("join")
def handle_join(data):
    room = data["room_code"]
    username = data["username"]
    join_room(room)
    emit("message", {"username": "System", "message": f"{username} has joined the chat!", "msg_id": "system_"+str(random.randint(1000,9999))}, room=room)

@socketio.on("message")
def handle_message(data):
    room = data["room_code"]
    username = data["username"]
    message = data["message"]
    msg_id = data.get("msg_id")
    if room not in chatrooms:
        return
    key = chatrooms[room]
    encrypted_message = encrypt_message(message, key)
    emit("message", {"username": username, "message": encrypted_message, "msg_id": msg_id}, room=room)

@socketio.on("delete_message")
def handle_delete_message(data):
    room = data["room_code"]
    msg_id = data["msg_id"]
    emit("delete_message", {"msg_id": msg_id}, room=room)

@app.route("/chat", methods=["GET", "POST"])
def chat_home():
    if request.method == "POST":
        action = request.form["action"]
        if action == "create":
            room = generate_room_code()
            chatrooms[room] = os.urandom(16)
            return redirect(url_for("chatroom", room_code=room))
        elif action == "join":
            room = request.form["room_code"].strip()
            if room in chatrooms:
                return redirect(url_for("chatroom", room_code=room))
            else:
                return "Invalid Room Code", 400
    return render_template("index.html")

@app.route("/chat/<room_code>")
def chatroom(room_code):
    if room_code not in chatrooms:
        return "Invalid Room Code", 400
    return render_template("chatroom.html", room_code=room_code)

@app.route("/get_key/<room_code>")
def get_key(room_code):
    if room_code not in chatrooms:
        return jsonify({"error": "Invalid Room Code"}), 400
    key_b64 = base64.b64encode(chatrooms[room_code]).decode("utf-8")
    return jsonify({"key": key_b64})

# Forum Routes
@app.route("/forum")
def forum():
    posts = list(posts_collection.find({}))
    
    for post in posts:
        post["_id"] = str(post["_id"])
        if post["image"]:
            post["image"] = base64.b64encode(post["image"]).decode("utf-8")

    return render_template("forum.html", posts=posts)

@app.route("/submit_post", methods=["POST"])
def submit_post():
    title = request.form.get("title", "").strip()
    content = request.form.get("content", "").strip()
    image = request.files.get("image")

    if not title or not content:
        return "Title and Content are required", 400

    post_data = {"title": title, "content": content, "image": None, "comments": []}

    if image:
        image_data = image.read()
        post_data["image"] = Binary(image_data)

    post_id = posts_collection.insert_one(post_data).inserted_id
    return redirect(url_for("post_view", post_id=str(post_id)))

@app.route("/post/<string:post_id>")
def post_view(post_id):
    try:
        post = posts_collection.find_one({'_id': ObjectId(post_id)})
        if not post:
            return "Post not found", 404

        post["_id"] = str(post["_id"])

        if post["image"]:
            post["image"] = base64.b64encode(post["image"]).decode("utf-8")

        return render_template("post.html", post=post)
    except Exception:
        return "Invalid Post ID", 400

@app.route("/post/<string:post_id>/comment", methods=["POST"])
def add_comment(post_id):
    comment_text = request.form.get("comment", "").strip()
    if not comment_text:
        return "Comment cannot be empty", 400

    try:
        posts_collection.update_one(
            {"_id": ObjectId(post_id)}, 
            {"$push": {"comments": {"user": "Anonymous", "text": comment_text}}}
        )
        return redirect(url_for("post_view", post_id=post_id))
    except Exception:
        return "Invalid Post ID", 400


class CustomWebEnginePage(QWebEnginePage):
    def __init__(self, parent=None):
        super().__init__(parent)

    def createWindow(self, _type):
        new_browser = QWebEngineView()
        new_browser.setPage(CustomWebEnginePage(new_browser))
        parent_window.add_new_tab_widget(new_browser, "New Tab")
        return new_browser.page()

class WraithBrowser(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Wraith Browser")
        self.setGeometry(100, 100, 1024, 768)
        
        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        
        self.new_tab_button = QPushButton("+")
        self.new_tab_button.setFixedSize(20, 20)
        self.new_tab_button.clicked.connect(self.add_new_tab)
        
        self.tabs.setCornerWidget(self.new_tab_button)
        
        main_layout = QVBoxLayout()
        main_layout.addWidget(self.tabs)
        
        container = QWidget()
        container.setLayout(main_layout)
        self.setCentralWidget(container)
        
        self.configure_tor_proxy()

        time.sleep(5)  

        try:
            onion_file = os.path.join(os.path.dirname(__file__), "tor", "hidden_service", "hostname")
            if os.path.exists(onion_file):
                with open(onion_file, "r") as f:
                    onion_address = f.read().strip()
                    self.add_new_tab(f"http://{onion_address}", "Home")
            else:
                print("Onion hostname file not found, using default address")
                self.add_new_tab("http://127.0.0.1:8000", "Home")
        except Exception as e:
            print(f"Error reading onion address: {e}")
            self.add_new_tab("http://127.0.0.1:8000", "Home")

    def configure_tor_proxy(self):
        proxy = QNetworkProxy()
        proxy.setType(QNetworkProxy.ProxyType.Socks5Proxy)
        proxy.setHostName("127.0.0.1")
        proxy.setPort(9050)
        QNetworkProxy.setApplicationProxy(proxy)
    
    def add_new_tab(self, url="http://", label="New Tab"):
        if not isinstance(url, str):
            url = "http://"
        
        browser = QWebEngineView()
        browser.setPage(CustomWebEnginePage(browser))
        browser.setUrl(QUrl(url))
        
        back_button = QPushButton("◀")
        back_button.clicked.connect(browser.back)
        
        reload_button = QPushButton("⟳")
        reload_button.clicked.connect(browser.reload)
        
        forward_button = QPushButton("▶")
        forward_button.clicked.connect(browser.forward)
        
        url_bar = QLineEdit()
        url_bar.setPlaceholderText("Enter URL...")
        url_bar.setText(url)
        url_bar.returnPressed.connect(lambda: self.load_url(url_bar, browser))
        
        top_layout = QHBoxLayout()
        top_layout.addWidget(back_button)
        top_layout.addWidget(reload_button)
        top_layout.addWidget(forward_button)
        top_layout.addWidget(url_bar)
        
        tab_layout = QVBoxLayout()
        tab_layout.addLayout(top_layout)
        tab_layout.addWidget(browser)
        
        tab_container = QWidget()
        tab_container.setLayout(tab_layout)
        
        self.tabs.addTab(tab_container, label)
        self.tabs.setCurrentWidget(tab_container)
    
    def add_new_tab_widget(self, browser, label="New Tab"):
        tab_layout = QVBoxLayout()
        tab_layout.addWidget(browser)
        
        tab_container = QWidget()
        tab_container.setLayout(tab_layout)
        
        self.tabs.addTab(tab_container, label)
        self.tabs.setCurrentWidget(tab_container)
    
    def load_url(self, url_bar, browser):
        url = url_bar.text().strip()
        if not url.startswith("http"):
            url = "http://" + url
        browser.setUrl(QUrl(url))
    
    def close_tab(self, index):
        if self.tabs.count() > 1:
            self.tabs.removeTab(index)

def run_tor():
    print("Starting Tor...")

    tor_exe = os.path.join(os.path.dirname(__file__), "tor", "tor.exe")
    torrc_path = os.path.join(os.path.dirname(__file__), "tor", "torrc")
    app_path = os.path.join(os.path.dirname(__file__), "app.py")
    print(f"Application path: {app_path}")

    tor_dir = os.path.dirname(torrc_path)
    data_dir = os.path.join(tor_dir, "Data")
    hidden_dir = os.path.join(tor_dir, "hidden_service")

    os.makedirs(data_dir, exist_ok=True)
    os.makedirs(hidden_dir, exist_ok=True)

    with open(torrc_path, "w") as f:
        f.write(f"""SocksPort 9050
ControlPort 9051
DataDirectory {data_dir}
HiddenServiceDir {hidden_dir}
HiddenServicePort 80 127.0.0.1:8000
        """)

    tor_process = subprocess.Popen([
        tor_exe, "-f", torrc_path
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    threading.Thread(target=lambda: print_stream(tor_process.stdout, "Tor"), daemon=True).start()
    threading.Thread(target=lambda: print_stream(tor_process.stderr, "Tor Error"), daemon=True).start()

    return tor_process

def run_flask():
    print("Starting Flask server...")
    socketio.run(app, host="127.0.0.1", port=8000, debug=True, use_reloader=False)

def main():
    global parent_window
    
    tor_process = run_tor()
    
    print("Waiting for Tor to initialize...")
    
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    print("Waiting for Flask to initialize...")
    time.sleep(3)
    
    print("Starting Wraith Browser...")
    app = QApplication(sys.argv)
    window = WraithBrowser()
    parent_window = window
    window.show()
    
    exit_code = app.exec()
    print("Shutting down...")
    tor_process.terminate()
    tor_process.wait()
    print("Tor process terminated")
    
    sys.exit(exit_code)

if __name__ == "__main__":
    main()