from flask import Flask, render_template, jsonify, request, send_from_directory, redirect, url_for, session
import psutil
import time
import platform
import socket
import subprocess
import json
import os
import signal
import requests
import shutil
import threading
import traceback
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import secrets
import re

# Library speedtest Python (fallback kalau Ookla CLI nggak ada)
try:
    import speedtest as st_lib
except ImportError:
    st_lib = None

app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.environ.get("RIOOS_SECRET_KEY") or secrets.token_hex(32),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("RIOOS_HTTPS", "0") == "1",
    PERMANENT_SESSION_LIFETIME=__import__("datetime").timedelta(hours=8),
)
HOSTNAME = platform.node()
OS_TYPE = platform.system()

# ==========================================
# CONFIG TELEGRAM (BUAT NOTIF AUTO-BLOCK)
# ==========================================
TG_BOT_TOKEN = os.environ.get("TG_BOT_TOKEN", "").strip()
TG_CHAT_ID = os.environ.get("TG_CHAT_ID", "").strip()

# ==========================================
# DATABASE SEDERHANA (JSON)
# ==========================================
SHARED_FOLDER = os.path.join(os.getcwd(), 'shared_files')
os.makedirs(SHARED_FOLDER, exist_ok=True)
APPS_FILE = 'apps.json'
NETWORK_DB = 'network_devices.json'
USERS_FILE = 'users.json'
LOG_FILE = 'network_logs.txt'

def load_json(file, default):
    if os.path.exists(file):
        try:
            with open(file, 'r') as f: return json.load(f)
        except: pass
    return default

def save_json(file, data):
    with open(file, 'w') as f: json.dump(data, f, indent=4)

def log_event(msg):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, 'a') as f:
        f.write(f"[{ts}] {msg}\n")


# ==========================================
# AUTENTIKASI & ROLE ACCESS CONTROL (RBAC)
# ==========================================
def load_users():
    users = load_json(USERS_FILE, {})
    if not users:
        admin_name = os.environ.get("RIOOS_ADMIN_USERNAME", "").strip()
        admin_password = os.environ.get("RIOOS_ADMIN_PASSWORD", "")
        if admin_name and admin_password:
            users[admin_name] = {
                "password": generate_password_hash(admin_password),
                "role": "admin", "active": True,
                "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            }
            save_json(USERS_FILE, users)
    return users

users_db = load_users()

@app.before_request
def protect_state_changes():
    if request.method in {"POST", "PUT", "PATCH", "DELETE"} and request.path.startswith("/api/"):
        origin = request.headers.get("Origin")
        if origin:
            from urllib.parse import urlparse
            if urlparse(origin).netloc != request.host:
                return jsonify({"error": "Permintaan lintas situs ditolak."}), 403

def current_user():
    username = session.get("username")
    user = users_db.get(username) if username else None
    if not user or not user.get("active", False):
        session.clear()
        return None
    return {"username": username, "role": user.get("role", "user")}

def api_error(message, status):
    return jsonify({"error": message}), status

def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not current_user():
            if request.path.startswith("/api/"):
                return api_error("Login diperlukan.", 401)
            return redirect(url_for("login_page"))
        return fn(*args, **kwargs)
    return wrapper

def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = current_user()
        if not user:
            return api_error("Login diperlukan.", 401)
        if user["role"] != "admin":
            return api_error("Akses ditolak. Khusus admin.", 403)
        return fn(*args, **kwargs)
    return wrapper

@app.route("/login", methods=["GET"])
def login_page():
    if current_user():
        return redirect(url_for("index"))
    return render_template("login.html", setup_missing=not bool(users_db))

@app.route("/api/auth/login", methods=["POST"])
def auth_login():
    data = request.get_json(silent=True) or request.form
    username = str(data.get("username", "")).strip()
    password = str(data.get("password", ""))
    user = users_db.get(username)
    if not user or not user.get("active", False) or not check_password_hash(user.get("password", ""), password):
        return api_error("Username atau password salah, atau akun belum diizinkan.", 401)
    session.clear()
    session["username"] = username
    session.permanent = True
    return jsonify({"success": True, "user": {"username": username, "role": user.get("role", "user")}})

@app.route("/api/auth/logout", methods=["POST"])
def auth_logout():
    session.clear()
    return jsonify({"success": True})

@app.route("/api/auth/me", methods=["GET"])
@login_required
def auth_me():
    return jsonify(current_user())

@app.route("/api/admin/users", methods=["GET"])
@admin_required
def admin_list_users():
    return jsonify([{"username": n, "role": d.get("role", "user"), "active": bool(d.get("active", False))}
                    for n, d in users_db.items()])

@app.route("/api/admin/users", methods=["POST"])
@admin_required
def admin_create_user():
    data = request.get_json(silent=True) or {}
    username, password = str(data.get("username", "")).strip(), str(data.get("password", ""))
    if not re.fullmatch(r"[A-Za-z0-9_.-]{3,32}", username):
        return api_error("Username 3-32 karakter: huruf, angka, titik, _ atau -.", 400)
    if len(password) < 10:
        return api_error("Password minimal 10 karakter.", 400)
    if username in users_db:
        return api_error("Username sudah digunakan.", 409)
    users_db[username] = {"password": generate_password_hash(password), "role": "user",
                          "active": bool(data.get("active", True)),
                          "created_at": time.strftime("%Y-%m-%d %H:%M:%S")}
    save_json(USERS_FILE, users_db)
    log_event(f"Admin {session.get('username')} membuat akun user {username}")
    return jsonify({"success": True}), 201

@app.route("/api/admin/users/<username>", methods=["PATCH", "DELETE"])
@admin_required
def admin_update_user(username):
    if username not in users_db:
        return api_error("User tidak ditemukan.", 404)
    if users_db[username].get("role") == "admin":
        return api_error("Akun admin tidak dapat diubah dari panel user.", 403)
    if request.method == "DELETE":
        del users_db[username]
        save_json(USERS_FILE, users_db)
        log_event(f"Admin {session.get('username')} menghapus user {username}")
        return jsonify({"success": True})
    data = request.get_json(silent=True) or {}
    if "active" in data:
        users_db[username]["active"] = bool(data["active"])
    if data.get("password"):
        if len(data["password"]) < 10:
            return api_error("Password minimal 10 karakter.", 400)
        users_db[username]["password"] = generate_password_hash(data["password"])
    save_json(USERS_FILE, users_db)
    log_event(f"Admin {session.get('username')} memperbarui user {username}")
    return jsonify({"success": True})


# Init DB
devices_db = load_json(NETWORK_DB, {}) # Format: {"MAC": {"name": "HP Mama", "status": "allowed"}}
apps_db = load_json(APPS_FILE, {"telegram_bot": {"name": "🤖 Rio Telegram Bot", "cmd": ["python3", "bot.py"], "pid": None}})

last_net = psutil.net_io_counters()
last_time = time.time()
psutil.cpu_percent(interval=None)

# ==========================================
# FUNGSI-FUNGSI SISTEM & APPS
# ==========================================
def is_running(pid):
    if pid is None: return False
    try: os.kill(pid, 0); return True
    except OSError: return False

def stop_process(cfg):
    pid = cfg.get("pid")
    script = cfg["cmd"][-1] if len(cfg["cmd"]) > 1 else ""
    if pid:
        try: os.killpg(os.getpgid(pid), 9)
        except:
            try: os.kill(pid, 9)
            except: pass
    if script.endswith('.py') and OS_TYPE == "Linux":
        subprocess.run(["pkill", "-9", "-f", script], capture_output=True)

@app.route('/api/apps', methods=['GET'])
@admin_required
def get_apps():
    return jsonify([{"id": k, "name": v["name"], "status": "Running" if is_running(v["pid"]) else "Stopped", "pid": v["pid"]} for k, v in apps_db.items()])

@app.route('/api/apps/add', methods=['POST'])
@admin_required
def add_app():
    data = request.json
    apps_db[data['id']] = {"name": data['name'], "cmd": data['cmd'].split(), "pid": None}
    save_json(APPS_FILE, apps_db)
    return jsonify({"success": True})

@app.route('/api/apps/delete/<app_id>', methods=['DELETE'])
@admin_required
def delete_app(app_id):
    if app_id in apps_db:
        if is_running(apps_db[app_id]["pid"]): stop_process(apps_db[app_id])
        del apps_db[app_id]
        save_json(APPS_FILE, apps_db)
        return jsonify({"success": True})
    return jsonify({"error": "Not found"}), 404

@app.route('/api/apps/<app_id>/start', methods=['POST'])
@admin_required
def start_app(app_id):
    if app_id in apps_db:
        cfg = apps_db[app_id]
        if not is_running(cfg["pid"]):
            log_file = open(f"{app_id}.log", "w")
            process = subprocess.Popen(cfg["cmd"], stdout=log_file, stderr=subprocess.STDOUT, start_new_session=True)
            cfg["pid"] = process.pid
            save_json(APPS_FILE, apps_db)
            return jsonify({"success": True})
    return jsonify({"error": "Gagal"}), 400

@app.route('/api/apps/<app_id>/stop', methods=['POST'])
@admin_required
def stop_app(app_id):
    if app_id in apps_db:
        stop_process(apps_db[app_id])
        apps_db[app_id]["pid"] = None
        save_json(APPS_FILE, apps_db)
        return jsonify({"success": True})
    return jsonify({"error": "Gagal"}), 400

@app.route('/api/apps/<app_id>/logs', methods=['GET'])
@admin_required
def get_logs(app_id):
    log_path = f"{app_id}.log"
    if os.path.exists(log_path):
        with open(log_path, 'r', errors='ignore') as f: return jsonify({"logs": "".join(f.readlines()[-50:])})
    return jsonify({"logs": "Belum ada log."})

# ==========================================
# FUNGSI NETWORK (SCAN, BLOCK, BANDWIDTH)
# ==========================================
def scan_network():
    """Scan jaringan pakai arp-scan (butuh sudo)"""
    found_devices = []
    try:
        # Coba pakai arp-scan dulu
        result = subprocess.run(['sudo', 'arp-scan', '--localnet'], capture_output=True, text=True, timeout=30)
        lines = result.stdout.split('\n')
        for line in lines:
            parts = line.split()
            if len(parts) >= 2 and parts[1].count(':') == 5: # Cek format MAC
                ip, mac = parts[0], parts[1].upper()
                # Skip broadcast
                if mac == 'FF:FF:FF:FF:FF:FF': continue
                
                # Cek di DB
                if mac not in devices_db:
                    devices_db[mac] = {"name": "Unknown Device", "status": "allowed"}
                    log_event(f"New device detected: {ip} | {mac}")
                    # AUTO BLOCK & NOTIF
                    devices_db[mac]["status"] = "blocked"
                    block_mac(mac)
                    send_tg_notif(f"⚠️ *WARNING: UNKNOWN DEVICE!*\nIP: {ip}\nMAC: {mac}\nStatus: AUTO-BLOCKED")
                    
                found_devices.append({
                    "ip": ip, "mac": mac, 
                    "name": devices_db[mac]["name"], 
                    "status": devices_db[mac]["status"]
                })
        save_json(NETWORK_DB, devices_db)
    except Exception as e:
        return {"error": str(e)}
    return found_devices

def block_mac(mac):
    """Block MAC pakai iptables"""
    # Hapus rule lama dulu biar ga duplikat
    subprocess.run(['sudo', 'iptables', '-D', 'INPUT', '-m', 'mac', '--mac-source', mac, '-j', 'DROP'], capture_output=True)
    # Tambah rule block
    subprocess.run(['sudo', 'iptables', '-A', 'INPUT', '-m', 'mac', '--mac-source', mac, '-j', 'DROP'], capture_output=True)
    log_event(f"MAC Blocked: {mac}")

def unblock_mac(mac):
    """Unblock MAC"""
    subprocess.run(['sudo', 'iptables', '-D', 'INPUT', '-m', 'mac', '--mac-source', mac, '-j', 'DROP'], capture_output=True)
    log_event(f"MAC Unblocked: {mac}")

def send_tg_notif(msg):
    if not TG_BOT_TOKEN or not TG_CHAT_ID: return
    try:
        url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": TG_CHAT_ID, "text": msg, "parse_mode": "Markdown"}, timeout=5)
    except: pass

@app.route('/api/network/scan')
@admin_required
def api_scan():
    devices = scan_network()
    return jsonify(devices)

@app.route('/api/network/device/<mac>/<action>', methods=['POST'])
@admin_required
def api_device_action(mac, action):
    if mac in devices_db:
        if action == 'block':
            devices_db[mac]['status'] = 'blocked'
            block_mac(mac)
        elif action == 'allow':
            devices_db[mac]['status'] = 'allowed'
            unblock_mac(mac)
        elif action == 'rename':
            new_name = request.json.get('name', 'Unknown')
            devices_db[mac]['name'] = new_name
            log_event(f"Device Renamed: {mac} -> {new_name}")
        save_json(NETWORK_DB, devices_db)
        return jsonify({"success": True})
    return jsonify({"error": "MAC not found"}), 404

@app.route('/api/network/logs')
@admin_required
def api_logs():
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, 'r') as f: return jsonify({"logs": f.readlines()[-50:]})
    return jsonify({"logs": []})

# ==========================================
# API STATS & SYSTEM
# ==========================================
@app.route('/')
@login_required
def index(): return render_template('index.html', hostname=HOSTNAME, user=current_user())

# --- Cache ISP/IP publik: jarang berubah, diambil di background thread (nggak ngeblok request) ---
_isp = {"value": "Memuat...", "ts": 0}
ISP_TTL = 600  # detik

def _refresh_isp():
    try:
        res = requests.get("http://ip-api.com/json/?fields=isp,query", timeout=3).json()
        _isp["value"] = f"{res.get('isp')} ({res.get('query')})"
    except: pass

def get_isp():
    if time.time() - _isp["ts"] > ISP_TTL:
        _isp["ts"] = time.time()  # tandai dulu biar nggak spawn thread dobel, walau fetch gagal
        threading.Thread(target=_refresh_isp, daemon=True).start()
    return _isp["value"]

# --- Cache hasil stats 1 detik + lock ---
# Kalau ada beberapa tab/client, atau request numpuk, hitungannya nggak diulang-ulang
# dan angka CPU% / bandwidth tetap akurat (nggak diukur di jendela waktu yang terlalu pendek).
_stats_lock = threading.Lock()
_stats_cache = {"data": None, "ts": 0}
STATS_TTL = 1.0

def build_stats():
    global last_net, last_time
    uptime_seconds = time.time() - psutil.boot_time()
    cpu_usage = psutil.cpu_percent(interval=None) 
    cpu_temp = 0
    try:
        temps = psutil.sensors_temperatures()
        if temps:
            for name, entries in temps.items():
                for entry in entries:
                    if entry.current > 0: cpu_temp = round(entry.current); break
                if cpu_temp > 0: break
    except: pass
    try:
        _f = psutil.cpu_freq()
        cpu_freq = round(_f.current) if _f else 0
    except: cpu_freq = 0
    
    ram, swap, disk = psutil.virtual_memory(), psutil.swap_memory(), psutil.disk_usage('/')
    current_net, current_time = psutil.net_io_counters(), time.time()
    time_diff = current_time - last_time
    up_speed = (current_net.bytes_sent - last_net.bytes_sent) / time_diff if time_diff > 0 else 0
    down_speed = (current_net.bytes_recv - last_net.bytes_recv) / time_diff if time_diff > 0 else 0
    last_net, last_time = current_net, current_time

    # Info WiFi/LAN
    iface_info = []
    for name, addrs in psutil.net_if_addrs().items():
        if name == 'lo': continue
        ip = next((a.address for a in addrs if a.family == socket.AF_INET), "-")
        if ip != "-": iface_info.append({"name": name, "ip": ip})

    return {
        "cpu": {"usage": cpu_usage, "cores": psutil.cpu_count(), "temp": cpu_temp, "freq": cpu_freq},
        "ram": {"percent": ram.percent, "used": round(ram.used / (1024**2), 1), "total": round(ram.total / (1024**2), 1)},
        "swap": {"percent": swap.percent, "used": round(swap.used / (1024**2), 1), "total": round(swap.total / (1024**2), 1)},
        "disk": {"percent": disk.percent, "used": round(disk.used / (1024**3), 1), "total": round(disk.total / (1024**3), 1)},
        "net": {"up": up_speed, "down": down_speed},
        "uptime": time.strftime("%H:%M:%S", time.gmtime(uptime_seconds)),
        "network": {"interfaces": iface_info, "isp": get_isp()}
    }

@app.route('/api/stats')
@login_required
def get_stats():
    with _stats_lock:
        if _stats_cache["data"] is None or time.time() - _stats_cache["ts"] > STATS_TTL:
            _stats_cache["data"] = build_stats()
            _stats_cache["ts"] = time.time()
        return jsonify(_stats_cache["data"])

@app.route('/api/terminal', methods=['POST'])
@admin_required
def run_command():
    cmd = request.json.get('cmd')
    if not cmd: return jsonify({"output": "Perintah kosong."})
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
        return jsonify({"output": result.stdout + result.stderr if result.stdout + result.stderr else "[Berhasil]"})
    except Exception as e: return jsonify({"output": f"Error: {str(e)}"})

@app.route('/api/processes')
@admin_required
def get_processes():
    procs = []
    for p in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
        try: procs.append(p.info)
        except: pass
    return jsonify(sorted(procs, key=lambda x: x['cpu_percent'] or 0, reverse=True)[:50])

@app.route('/api/process/kill/<int:pid>', methods=['POST'])
@admin_required
def kill_process(pid):
    try: os.kill(pid, 9); return jsonify({"success": True})
    except Exception as e: return jsonify({"error": str(e)}), 500

# ==========================================
# SPEEDTEST
# ==========================================
# Jalan di thread terpisah + di-polling frontend, jadi nggak ada request HTTP
# yang ketahan 30-60 detik. Error apa pun (termasuk SystemExit dari library)
# ketangkap, dicetak lengkap di terminal, dan dikirim ke UI sebagai pesan error.
_st_lock = threading.Lock()
_st_state = {"status": "idle", "result": None, "error": None}

def _do_speedtest():
    ookla_path = "/usr/local/bin/speedtest"

    # 1. Ookla CLI (kalau ada)
    if os.path.exists(ookla_path):
        result = subprocess.run([ookla_path, "--format=json", "--accept-license", "--accept-gdpr"], capture_output=True, text=True, timeout=90)
        raw_out = result.stdout.strip()
        if result.returncode == 0 and raw_out:
            data = json.loads(raw_out[raw_out.find('{'):])
            return {
                "download": round(data['download']['bandwidth'] * 8 / 1_000_000, 2),
                "upload": round(data['upload']['bandwidth'] * 8 / 1_000_000, 2),
                "ping": round(data['ping']['latency'], 2),
                "server": data['server']['name']
            }

    # 2. Library Python speedtest-cli
    if st_lib:
        st = st_lib.Speedtest(secure=True)
        st.get_best_server()
        dl = round(st.download() / 1_000_000, 2)
        ul = round(st.upload() / 1_000_000, 2)
        return {"download": dl, "upload": ul, "ping": round(st.results.ping, 2), "server": st.results.server['name']}

    raise RuntimeError("Library speedtest belum terpasang (pip install speedtest-cli).")

def _speedtest_worker():
    try:
        result = _do_speedtest()
        _st_state.update(status="done", result=result, error=None)
    except BaseException as e:
        traceback.print_exc()  # detail lengkap muncul di terminal tempat app.py jalan
        _st_state.update(status="error", result=None, error=f"{type(e).__name__}: {e}")

@app.route('/api/speedtest/start', methods=['POST'])
@login_required
def speedtest_start():
    with _st_lock:
        if _st_state["status"] == "running":
            return jsonify({"status": "running"})
        _st_state.update(status="running", result=None, error=None)
    threading.Thread(target=_speedtest_worker, daemon=True).start()
    return jsonify({"status": "running"})

@app.route('/api/speedtest/status')
@login_required
def speedtest_status():
    return jsonify(_st_state)

# ==========================================
# FILE SHARING (dipulihkan dari versi sebelumnya, dipakai tab Files)
# ==========================================
@app.route('/api/files', methods=['GET'])
@login_required
def list_files():
    files = []
    for filename in os.listdir(SHARED_FOLDER):
        path = os.path.join(SHARED_FOLDER, filename)
        if os.path.isfile(path): files.append({"name": filename, "size": round(os.path.getsize(path) / (1024**2), 2)})
    return jsonify(files)

@app.route('/api/upload', methods=['POST'])
@login_required
def upload_file():
    file = request.files.get('file')
    if file and file.filename != '':
        safe_name = secure_filename(file.filename)
        if not safe_name: return jsonify({"error": "Nama file tidak valid"}), 400
        file.save(os.path.join(SHARED_FOLDER, safe_name))
        return jsonify({"success": True})
    return jsonify({"error": "No file"}), 400

@app.route('/api/download/<filename>', methods=['GET'])
@login_required
def download_file(filename): return send_from_directory(SHARED_FOLDER, secure_filename(filename), as_attachment=True)

@app.route('/api/delete/<filename>', methods=['DELETE'])
@admin_required
def delete_file(filename):
    path = os.path.join(SHARED_FOLDER, secure_filename(filename))
    if os.path.isfile(path): os.remove(path); return jsonify({"success": True})
    return jsonify({"error": "Not found"}), 404

if __name__ == '__main__':
    if not any(u.get("role") == "admin" for u in users_db.values()):
        print("PERINGATAN: Admin belum dibuat. Set RIOOS_ADMIN_USERNAME dan RIOOS_ADMIN_PASSWORD, lalu restart.")
    app.run(host='0.0.0.0', port=5000, debug=False)
