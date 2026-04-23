from flask import Flask, send_from_directory, request, jsonify
from flask_socketio import SocketIO, join_room, emit
import requests
import mysql.connector
import os
import random
import string

app = Flask(__name__, static_folder="../front-end", static_url_path="")
socketio = SocketIO(app, cors_allowed_origins="*")

NGROK_URL = os.getenv("NGROK_URL")

def get_db():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="nexy"
    )


# ROTAS
@app.route("/")
def home():
    return send_from_directory(app.static_folder, "login.html")

@app.route("/loginpage")
def login_page():
    return send_from_directory(app.static_folder, "login.html")

@app.route("/registerpage")
def register_page():
    return send_from_directory(app.static_folder, "register.html")

@app.route("/dashboard")
def dashboard():
    return send_from_directory(app.static_folder, "dashboard.html")

@app.route("/chatpage")
def chat_page():
    return send_from_directory(app.static_folder, "chat.html")

@app.route("/meeting/<room>")
def meeting(room):
    return send_from_directory(app.static_folder, "meeting.html")

# CONFIG
@app.route("/config")
def config():
    base = NGROK_URL if NGROK_URL else request.host_url.rstrip("/")
    return jsonify({"base_url": base})

def gerar_codigo():
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))

@app.route("/criar_reuniao")
def criar_reuniao():
    codigo = gerar_codigo()
    base = NGROK_URL if NGROK_URL else request.host_url.rstrip("/")
    link = f"{base}/meeting/{codigo}"
    return jsonify({"codigo": codigo, "link": link})

# LOGIN
@app.route('/register', methods=['POST'])
def register():
    data = request.json
    conn = get_db()
    cursor = conn.cursor()

    try:
        cursor.execute(
            "INSERT INTO usuarios (nome, email, senha) VALUES (%s, %s, %s)",
            (data['nome'], data['email'], data['senha'])
        )
        conn.commit()
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"status": "erro", "msg": str(e)})

@app.route('/login', methods=['POST'])
def login():
    data = request.json
    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        "SELECT * FROM usuarios WHERE email=%s AND senha=%s",
        (data['email'], data['senha'])
    )

    user = cursor.fetchone()

    if user:
        return jsonify({
            "status": "ok",
            "nome": user["nome"],
            "id": user["id_usuario"]
        })
    else:
        return jsonify({"status": "erro"})

# IA
@app.route("/chat", methods=["POST"])
def chat_api():
    try:
        data = request.json
        msg = data.get("msg", "")

        print("CHAT RECEBIDO:", msg)

        r = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": "llama3.2",
    "prompt": f"""
Você é a Nexy, uma assistente de IA dentro de uma reunião.
Responda sempre em português do Brasil.
Seja direto, útil e inteligente.

Pergunta do usuário: {msg}
""",
    "stream": False
            },
            timeout=60
        )

        print("RESPOSTA OLLAMA:", r.text)

        return jsonify({
            "resposta": r.json().get("response", "Sem resposta")
        })

    except Exception as e:
        print("ERRO CHAT:", e)

        return jsonify({
            "resposta": "Erro no servidor de IA",
            "erro": str(e)
        })
        
@app.route("/sobre")
def sobre():
    return send_from_directory(app.static_folder, "sobre.html")
        
# SOCKET MULTIUSUÁRIO
@socketio.on("join")
def on_join(data):
    room = data["room"]
    nome = data.get("nome", "Usuário")

    join_room(room)

    emit("user_joined", {
        "id": request.sid,
        "nome": nome
    }, room=room)

    emit("all_users", {
        "users": list(socketio.server.manager.rooms['/'][room])
    }, to=request.sid)

@socketio.on("offer")
def offer(data):
    emit("offer", {
        "from": request.sid,
        "offer": data["offer"]
    }, to=data["to"])

@socketio.on("answer")
def answer(data):
    emit("answer", {
        "from": request.sid,
        "answer": data["answer"]
    }, to=data["to"])

@socketio.on("ice")
def ice(data):
    emit("ice", {
        "from": request.sid,
        "candidate": data["candidate"]
    }, to=data["to"])

@socketio.on("chat")
def chat(data):
    emit("chat", data, room=data["room"], include_self=False)

if __name__ == "__main__":
    socketio.run(app, port=5000, debug=True)
    
@socketio.on('disconnect')
def handle_disconnect():
    emit('user-disconnected', request.sid, broadcast=True)    