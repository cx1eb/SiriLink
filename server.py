from flask import Flask, request, render_template, jsonify
from flask import session, redirect, url_for
import threading
import subprocess
import json
import os
import datetime
import secrets
import string


app = Flask(__name__)

COMMAND_FILE = "templates\\commands.json"
LOG_FILE = "templates\\logs.json"
CONFIG_FILE = "templates\\config.json"


app.secret_key = "ChangeMeNow!"


def load_json(file):
    if not os.path.exists(file):
        return {}
    with open(file, "r") as f:
        return json.load(f)


def save_json(file, data):
    with open(file, "w") as f:
        json.dump(data, f, indent=4)


def log_event(ip, command, password_attempt, success):
    logs = load_json(LOG_FILE)
    if not isinstance(logs, list):
        logs = []

    logs.append({
        "time": str(datetime.datetime.now()),
        "ip": ip,
        "command": command,
        "password_attempt": password_attempt,
        "success": success
    })

    save_json(LOG_FILE, logs)


def execute_command(cmd):
    subprocess.Popen(cmd, shell=True)


@app.route("/login", methods=["POST"])
def login():
    password = request.form.get("password")
    config = load_json(CONFIG_FILE)

    if password == config.get("login_password"):
        session["authenticated"] = True
        return redirect(url_for("dashboard"))

    return render_template(
        "index.html",
        login_only=True,
        login_error="Wrong password"
    )



@app.route("/")
def dashboard():
    if not session.get("authenticated"):
        return render_template("index.html", login_only=True)

    commands = load_json(COMMAND_FILE)
    logs = load_json(LOG_FILE)

    if not isinstance(logs, list):
        logs = []

    logs = logs[-20:]

    return render_template(
        "index.html",
        commands=commands,
        logs=reversed(logs),
        login_only=False
    )


@app.route("/execute", methods=["POST"])
def execute():
    if not session.get("authenticated"):
        return jsonify({"status": "Unauthorized"}), 401

    data = request.json
    command_name = data.get("command")
    ip = request.remote_addr

    config = load_json(CONFIG_FILE)
    commands = load_json(COMMAND_FILE)

    if command_name not in commands:
        log_event(ip, command_name, None, False)
        return jsonify({"status": "Invalid command"}), 400

    if not commands[command_name]["enabled"]:
        log_event(ip, command_name, None, False)
        return jsonify({"status": "Command disabled"}), 403

    threading.Thread(
        target=execute_command,
        args=(commands[command_name]["command"],)
    ).start()

    log_event(ip, command_name, None, True)

    return jsonify({"status": "Executed"}), 200

from flask import abort

@app.route("/api/run/<command_name>", methods=["GET"])
def api_run_get(command_name):
    ip = request.remote_addr
    key = request.args.get("key", "")

    config = load_json(CONFIG_FILE)
    commands = load_json(COMMAND_FILE)

    if command_name not in commands:
        log_event(ip, command_name, key, False)
        abort(404)

    if key != config.get("api_password"):
        log_event(ip, command_name, key, False)
        abort(403)

    if not commands[command_name].get("enabled", False):
        log_event(ip, command_name, key, False)
        abort(403)

    threading.Thread(
        target=execute_command,
        args=(commands[command_name]["command"],)
    ).start()

    log_event(ip, command_name, key, True)
    return "OK"


@app.route("/save_command", methods=["POST"])
def save_command():
    if not session.get("authenticated"):
        return jsonify({"status": "Unauthorized"}), 401

    data = request.json
    name = data.get("name")
    cmd = data.get("command")
    enabled = data.get("enabled", True)

    commands = load_json(COMMAND_FILE)

    commands[name] = {
        "command": cmd,
        "enabled": enabled
    }

    save_json(COMMAND_FILE, commands)
    return jsonify({"status": "Saved"})


@app.route("/delete_command", methods=["POST"])
def delete_command():
    if not session.get("authenticated"):
        return jsonify({"status": "Unauthorized"}), 401

    name = request.json.get("name")
    commands = load_json(COMMAND_FILE)

    if name in commands:
        del commands[name]
        save_json(COMMAND_FILE, commands)

    return jsonify({"status": "Deleted"})


@app.route("/toggle", methods=["POST"])
def toggle():
    if not session.get("authenticated"):
        return jsonify({"status": "Unauthorized"}), 401

    data = request.json
    command_name = data.get("command")

    commands = load_json(COMMAND_FILE)

    if command_name in commands:
        commands[command_name]["enabled"] = not commands[command_name]["enabled"]
        save_json(COMMAND_FILE, commands)
        return jsonify({"status": "Toggled"}), 200

    return jsonify({"status": "Invalid"}), 400



@app.route("/update_passwords", methods=["POST"])
def update_passwords():
    if not session.get("authenticated"):
        return jsonify({"status": "Unauthorized"}), 401

    data = request.json
    login_pw = data.get("login_password")
    api_pw = data.get("api_password")

    config = load_json(CONFIG_FILE)

    if login_pw:
        config["login_password"] = login_pw
    if api_pw:
        config["api_password"] = api_pw

    save_json(CONFIG_FILE, config)

    return jsonify({"status": "Updated"})

@app.route("/generate_api_password", methods=["POST"])
def generate_api_password():
    if not session.get("authenticated"):
        return jsonify({"status": "Unauthorized"}), 401

    alphabet = string.ascii_letters + string.digits
    new_pw = ''.join(secrets.choice(alphabet) for _ in range(24))

    config = load_json(CONFIG_FILE)
    config["api_password"] = new_pw
    save_json(CONFIG_FILE, config)

    return jsonify({"password": new_pw})




if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
