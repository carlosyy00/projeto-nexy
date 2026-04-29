from flask import Flask, send_from_directory, request, jsonify, session, redirect
from flask_socketio import SocketIO, join_room, emit
from werkzeug.security import generate_password_hash, check_password_hash
import requests
import mysql.connector
import os
import random
import string

app = Flask(__name__, static_folder="../front-end", static_url_path="")

# 🔐 CONFIGURAÇÃO DE SEGURANÇA SESSION
app.secret_key = "nexy_secret_key"
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

socketio = SocketIO(app, cors_allowed_origins="*")

NGROK_URL = os.getenv("NGROK_URL")

def get_db():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="nexy"
    )

# ───────── ROTAS ─────────

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
    if "usuario" not in session:
        return redirect("/loginpage")
    return send_from_directory(app.static_folder, "dashboard.html")

@app.route("/chatpage")
def chat_page():
    if "usuario" not in session:
        return redirect("/loginpage")
    return send_from_directory(app.static_folder, "chat.html")

@app.route("/meeting/<room>")
def meeting(room):
    if "usuario" not in session:
        return redirect("/loginpage")
    return send_from_directory(app.static_folder, "meeting.html")

@app.route("/sobre")
def sobre():
    return send_from_directory(app.static_folder, "sobre.html")

# ───────── CONFIG ─────────

@app.route("/config")
def config():
    base = NGROK_URL if NGROK_URL else request.host_url.rstrip("/")
    return jsonify({"base_url": base})

def gerar_codigo():
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))

@app.route("/criar_reuniao")
def criar_reuniao():
    if "usuario" not in session:
        return redirect("/loginpage")

    codigo = gerar_codigo()
    base = NGROK_URL if NGROK_URL else request.host_url.rstrip("/")
    link = f"{base}/meeting/{codigo}"

    return jsonify({"codigo": codigo, "link": link})

# ───────── REGISTER ─────────

@app.route('/register', methods=['POST'])
def register():
    data = request.json

    nome = data.get('nome', '').strip()
    email = data.get('email', '').strip().lower()
    senha = data.get('senha', '').strip()

    conn = get_db()
    cursor = conn.cursor()

    senha_hash = generate_password_hash(senha, method='pbkdf2:sha256')

    try:
        cursor.execute(
            "INSERT INTO usuarios (nome, email, senha) VALUES (%s, %s, %s)",
            (nome, email, senha_hash)
        )
        conn.commit()
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"status": "erro", "msg": str(e)})

# ───────── LOGIN ─────────

@app.route('/login', methods=['POST'])
def login():
    data = request.json

    email = data.get('email', '').strip().lower()
    senha = data.get('senha', '').strip()

    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        "SELECT * FROM usuarios WHERE LOWER(email)=%s",
        (email,)
    )

    user = cursor.fetchone()

    # DEBUG (AGORA FUNCIONA)
    print("EMAIL:", email)
    print("USER:", user)

    if user:
        print("CHECK:", check_password_hash(user['senha'], senha))

    if user and check_password_hash(user['senha'], senha):

        session["usuario"] = user["nome"]
        session["id_usuario"] = user["id_usuario"]

        return jsonify({
            "status": "ok",
            "nome": user["nome"],
            "id": user["id_usuario"]
        })
    else:
        return jsonify({"status": "erro"})

# ───────── LOGOUT ─────────

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/loginpage")

# ───────── IA ─────────

@app.route("/chat", methods=["POST"])
def chat_api():
    try:
        data = request.json
        msg = data.get("msg", "").strip().lower()

        # 🔥 NORMALIZAÇÃO
        msg = msg.replace("oq", "o que")
        msg = msg.replace("q ", "que ")
        msg = msg.replace("vc", "você")

        # 🔥 RESPOSTAS FIXAS (DEMO PERFEITA)
        respostas_fixas = {
            "webrtc": "WebRTC é uma tecnologia que permite comunicação em tempo real (áudio, vídeo e dados) diretamente no navegador.",
            "instagram": "Instagram é uma rede social onde as pessoas compartilham fotos, vídeos e interagem com outros usuários.",
            "inteligencia artificial": "Inteligência Artificial é a área da computação que permite que máquinas simulem o pensamento humano.",
            "nexy": "Nexy é uma plataforma de videoconferência com inteligência artificial integrada."
        }

        for chave in respostas_fixas:
            if chave in msg:
                return jsonify({"resposta": respostas_fixas[chave]})

        # 🔥 IA LOCAL
        r = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": "phi",
                "prompt": f"Explique de forma simples: {msg}",
                "stream": False
            },
            timeout=30
        )

        resposta = r.json().get("response", "").strip()

        # 🔥 BLOQUEIA INGLÊS NA RAIZ
        palavras_ingles = [" is ", " are ", " the ", " and ", "with", "this", "that"]

        if any(p in resposta.lower() for p in palavras_ingles):
            resposta = "Não consegui responder corretamente em português. Tente reformular a pergunta."

        # 🔥 LIMPA TEXTO RUIM
        lixo = ["Pergunta", "Resposta", "Assistant", "Hello"]

        for palavra in lixo:
            resposta = resposta.replace(palavra, "")

        # 🔥 LIMITA TAMANHO
        if len(resposta) > 200:
            resposta = resposta[:200] + "..."

        return jsonify({"resposta": resposta})

    except Exception as e:
        print("ERRO CHAT:", e)
        return jsonify({"resposta": "Erro no servidor de IA"})
# ───────── SOCKET ─────────

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

@socketio.on('disconnect')
def handle_disconnect():
    emit('user-disconnected', request.sid, broadcast=True)

# ───────── START ─────────

if __name__ == "__main__":
    socketio.run(app, port=5000, debug=True)