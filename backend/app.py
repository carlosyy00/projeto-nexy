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


def usuario_logado():
    return "usuario" in session and "id_usuario" in session


def gerar_codigo():
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))


# ───────── ROTAS DE PÁGINAS ─────────

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
    if not usuario_logado():
        return redirect("/loginpage")
    return send_from_directory(app.static_folder, "dashboard.html")


@app.route("/chatpage")
def chat_page():
    if not usuario_logado():
        return redirect("/loginpage")
    return send_from_directory(app.static_folder, "chat.html")


@app.route("/meeting/<room>")
def meeting(room):
    if not usuario_logado():
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


# ───────── REGISTER ─────────

@app.route('/register', methods=['POST'])
def register():
    data = request.json

    nome = data.get('nome', '').strip()
    email = data.get('email', '').strip().lower()
    senha = data.get('senha', '').strip()

    if not nome or not email or not senha:
        return jsonify({"status": "erro", "msg": "Preencha todos os campos."})

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
    finally:
        cursor.close()
        conn.close()


# ───────── LOGIN ─────────

@app.route('/login', methods=['POST'])
def login():
    data = request.json

    email = data.get('email', '').strip().lower()
    senha = data.get('senha', '').strip()

    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        "SELECT * FROM usuarios WHERE LOWER(email) = %s",
        (email,)
    )

    user = cursor.fetchone()

    cursor.close()
    conn.close()

    if user and check_password_hash(user['senha'], senha):
        session["usuario"] = user["nome"]
        session["id_usuario"] = user["id_usuario"]

        return jsonify({
            "status": "ok",
            "nome": user["nome"],
            "id": user["id_usuario"]
        })

    return jsonify({"status": "erro"})


# ───────── LOGOUT ─────────

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/loginpage")


# ───────── CRIAÇÃO RÁPIDA DE REUNIÃO ─────────
# Essa rota é usada pelo botão "Criar reunião" do dashboard.
# Agora ela cria o link E salva a sala no banco.

@app.route("/criar_reuniao")
def criar_reuniao():
    if not usuario_logado():
        return redirect("/loginpage")

    codigo = gerar_codigo()
    base = NGROK_URL if NGROK_URL else request.host_url.rstrip("/")
    link = f"{base}/meeting/{codigo}"

    nome_sala = f"Sala {codigo}"
    id_criador = session.get("id_usuario")

    conn = get_db()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            INSERT INTO salas (nome_sala, link, id_criador)
            VALUES (%s, %s, %s)
            """,
            (nome_sala, link, id_criador)
        )
        conn.commit()
    finally:
        cursor.close()
        conn.close()

    return jsonify({"codigo": codigo, "link": link})


# ───────── CRUD 1: USUÁRIOS ─────────

@app.route("/usuarios")
def listar_usuarios():
    if not usuario_logado():
        return redirect("/loginpage")

    pagina = request.args.get("pagina", 1, type=int)
    limite = 10
    offset = (pagina - 1) * limite

    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT COUNT(*) AS total FROM usuarios")
    total = cursor.fetchone()["total"]

    cursor.execute(
        """
        SELECT id_usuario, nome, email, data_criacao
        FROM usuarios
        ORDER BY id_usuario DESC
        LIMIT %s OFFSET %s
        """,
        (limite, offset)
    )
    usuarios = cursor.fetchall()

    cursor.close()
    conn.close()

    total_paginas = (total + limite - 1) // limite

    html = """
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head>
        <meta charset="UTF-8">
        <title>Usuários - Nexy</title>
        <style>
            body { background:#0f172a; color:white; font-family:Arial; padding:30px; }
            a { color:#38bdf8; text-decoration:none; }
            table { width:100%; border-collapse:collapse; background:#1e293b; margin-top:20px; }
            th, td { padding:12px; border-bottom:1px solid #334155; text-align:left; }
            th { background:#020617; }
            .btn { padding:8px 12px; border-radius:6px; background:#3b82f6; color:white; display:inline-block; margin:5px 0; }
            .danger { background:#ef4444; }
            .pagination a { margin-right:8px; padding:6px 10px; background:#1e293b; border-radius:5px; }
        </style>
    </head>
    <body>
        <h1>Gerenciar Usuários</h1>
        <a class="btn" href="/dashboard">Voltar ao Dashboard</a>

        <table>
            <tr>
                <th>ID</th>
                <th>Nome</th>
                <th>Email</th>
                <th>Data de criação</th>
                <th>Ações</th>
            </tr>
    """

    for u in usuarios:
        html += f"""
            <tr>
                <td>{u['id_usuario']}</td>
                <td>{u['nome']}</td>
                <td>{u['email']}</td>
                <td>{u['data_criacao']}</td>
                <td>
                    <a class="btn" href="/usuarios/editar/{u['id_usuario']}">Editar</a>
                    <a class="btn danger" href="/usuarios/excluir/{u['id_usuario']}"
                       onclick="return confirm('Tem certeza que deseja excluir este usuário?')">Excluir</a>
                </td>
            </tr>
        """

    html += """
        </table>
        <div class="pagination">
            <p>Páginas:</p>
    """

    if total_paginas == 0:
        html += "<p>Nenhum usuário cadastrado.</p>"
    else:
        for p in range(1, total_paginas + 1):
            html += f"<a href='/usuarios?pagina={p}'>{p}</a>"

    html += """
        </div>
    </body>
    </html>
    """

    return html


@app.route("/usuarios/editar/<int:id_usuario>", methods=["GET", "POST"])
def editar_usuario(id_usuario):
    if not usuario_logado():
        return redirect("/loginpage")

    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        email = request.form.get("email", "").strip().lower()

        cursor.execute(
            """
            UPDATE usuarios
            SET nome = %s, email = %s
            WHERE id_usuario = %s
            """,
            (nome, email, id_usuario)
        )
        conn.commit()

        cursor.close()
        conn.close()

        return redirect("/usuarios")

    cursor.execute(
        "SELECT id_usuario, nome, email FROM usuarios WHERE id_usuario = %s",
        (id_usuario,)
    )
    usuario = cursor.fetchone()

    cursor.close()
    conn.close()

    if not usuario:
        return "Usuário não encontrado."

    return f"""
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head>
        <meta charset="UTF-8">
        <title>Editar Usuário - Nexy</title>
        <style>
            body {{ background:#0f172a; color:white; font-family:Arial; padding:30px; }}
            input {{ width:100%; max-width:400px; padding:10px; margin:8px 0; border-radius:6px; border:none; }}
            button, a {{ padding:10px 14px; background:#3b82f6; color:white; border:none; border-radius:6px; text-decoration:none; cursor:pointer; }}
        </style>
    </head>
    <body>
        <h1>Editar Usuário</h1>

        <form method="POST">
            <label>Nome:</label><br>
            <input type="text" name="nome" value="{usuario['nome']}" required><br>

            <label>Email:</label><br>
            <input type="email" name="email" value="{usuario['email']}" required><br><br>

            <button type="submit">Salvar alterações</button>
            <a href="/usuarios">Cancelar</a>
        </form>
    </body>
    </html>
    """


@app.route("/usuarios/excluir/<int:id_usuario>")
def excluir_usuario(id_usuario):
    if not usuario_logado():
        return redirect("/loginpage")

    # Evita o usuário apagar a própria conta enquanto está logado.
    if id_usuario == session.get("id_usuario"):
        return "Você não pode excluir o próprio usuário enquanto está logado. <br><a href='/usuarios'>Voltar</a>"

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute(
        "DELETE FROM usuarios WHERE id_usuario = %s",
        (id_usuario,)
    )
    conn.commit()

    cursor.close()
    conn.close()

    return redirect("/usuarios")


# ───────── CRUD 2: SALAS ─────────

@app.route("/salas")
def listar_salas():
    if not usuario_logado():
        return redirect("/loginpage")

    pagina = request.args.get("pagina", 1, type=int)
    limite = 10
    offset = (pagina - 1) * limite

    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT COUNT(*) AS total FROM salas")
    total = cursor.fetchone()["total"]

    cursor.execute(
        """
        SELECT id_sala, nome_sala, link, id_criador
        FROM salas
        ORDER BY id_sala DESC
        LIMIT %s OFFSET %s
        """,
        (limite, offset)
    )
    salas = cursor.fetchall()

    cursor.close()
    conn.close()

    total_paginas = (total + limite - 1) // limite

    html = """
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head>
        <meta charset="UTF-8">
        <title>Salas - Nexy</title>
        <style>
            body { background:#0f172a; color:white; font-family:Arial; padding:30px; }
            a { color:#38bdf8; text-decoration:none; }
            table { width:100%; border-collapse:collapse; background:#1e293b; margin-top:20px; }
            th, td { padding:12px; border-bottom:1px solid #334155; text-align:left; }
            th { background:#020617; }
            .btn { padding:8px 12px; border-radius:6px; background:#3b82f6; color:white; display:inline-block; margin:5px 0; }
            .danger { background:#ef4444; }
            .pagination a { margin-right:8px; padding:6px 10px; background:#1e293b; border-radius:5px; }
        </style>
    </head>
    <body>
        <h1>Gerenciar Salas</h1>
        <a class="btn" href="/dashboard">Voltar ao Dashboard</a>
        <a class="btn" href="/salas/nova">Nova Sala</a>

        <table>
            <tr>
                <th>ID</th>
                <th>Nome da sala</th>
                <th>Link</th>
                <th>ID Criador</th>
                <th>Ações</th>
            </tr>
    """

    for s in salas:
        html += f"""
            <tr>
                <td>{s['id_sala']}</td>
                <td>{s['nome_sala']}</td>
                <td><a href="{s['link']}" target="_blank">Abrir link</a></td>
                <td>{s['id_criador']}</td>
                <td>
                    <a class="btn" href="/salas/editar/{s['id_sala']}">Editar</a>
                    <a class="btn danger" href="/salas/excluir/{s['id_sala']}"
                       onclick="return confirm('Tem certeza que deseja excluir esta sala?')">Excluir</a>
                </td>
            </tr>
        """

    html += """
        </table>
        <div class="pagination">
            <p>Páginas:</p>
    """

    if total_paginas == 0:
        html += "<p>Nenhuma sala cadastrada.</p>"
    else:
        for p in range(1, total_paginas + 1):
            html += f"<a href='/salas?pagina={p}'>{p}</a>"

    html += """
        </div>
    </body>
    </html>
    """

    return html


@app.route("/salas/nova", methods=["GET", "POST"])
def nova_sala():
    if not usuario_logado():
        return redirect("/loginpage")

    if request.method == "POST":
        nome_sala = request.form.get("nome_sala", "").strip()

        if not nome_sala:
            return "Nome da sala é obrigatório. <br><a href='/salas/nova'>Voltar</a>"

        codigo = gerar_codigo()
        base = NGROK_URL if NGROK_URL else request.host_url.rstrip("/")
        link = f"{base}/meeting/{codigo}"
        id_criador = session.get("id_usuario")

        conn = get_db()
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO salas (nome_sala, link, id_criador)
            VALUES (%s, %s, %s)
            """,
            (nome_sala, link, id_criador)
        )
        conn.commit()

        cursor.close()
        conn.close()

        return redirect("/salas")

    return """
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head>
        <meta charset="UTF-8">
        <title>Nova Sala - Nexy</title>
        <style>
            body { background:#0f172a; color:white; font-family:Arial; padding:30px; }
            input { width:100%; max-width:400px; padding:10px; margin:8px 0; border-radius:6px; border:none; }
            button, a { padding:10px 14px; background:#3b82f6; color:white; border:none; border-radius:6px; text-decoration:none; cursor:pointer; }
        </style>
    </head>
    <body>
        <h1>Nova Sala</h1>

        <form method="POST">
            <label>Nome da sala:</label><br>
            <input type="text" name="nome_sala" required><br><br>

            <button type="submit">Criar sala</button>
            <a href="/salas">Cancelar</a>
        </form>
    </body>
    </html>
    """


@app.route("/salas/editar/<int:id_sala>", methods=["GET", "POST"])
def editar_sala(id_sala):
    if not usuario_logado():
        return redirect("/loginpage")

    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    if request.method == "POST":
        nome_sala = request.form.get("nome_sala", "").strip()
        link = request.form.get("link", "").strip()

        cursor.execute(
            """
            UPDATE salas
            SET nome_sala = %s, link = %s
            WHERE id_sala = %s
            """,
            (nome_sala, link, id_sala)
        )
        conn.commit()

        cursor.close()
        conn.close()

        return redirect("/salas")

    cursor.execute(
        "SELECT id_sala, nome_sala, link FROM salas WHERE id_sala = %s",
        (id_sala,)
    )
    sala = cursor.fetchone()

    cursor.close()
    conn.close()

    if not sala:
        return "Sala não encontrada."

    return f"""
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head>
        <meta charset="UTF-8">
        <title>Editar Sala - Nexy</title>
        <style>
            body {{ background:#0f172a; color:white; font-family:Arial; padding:30px; }}
            input {{ width:100%; max-width:600px; padding:10px; margin:8px 0; border-radius:6px; border:none; }}
            button, a {{ padding:10px 14px; background:#3b82f6; color:white; border:none; border-radius:6px; text-decoration:none; cursor:pointer; }}
        </style>
    </head>
    <body>
        <h1>Editar Sala</h1>

        <form method="POST">
            <label>Nome da sala:</label><br>
            <input type="text" name="nome_sala" value="{sala['nome_sala']}" required><br>

            <label>Link:</label><br>
            <input type="text" name="link" value="{sala['link']}" required><br><br>

            <button type="submit">Salvar alterações</button>
            <a href="/salas">Cancelar</a>
        </form>
    </body>
    </html>
    """


@app.route("/salas/excluir/<int:id_sala>")
def excluir_sala(id_sala):
    if not usuario_logado():
        return redirect("/loginpage")

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute(
        "DELETE FROM salas WHERE id_sala = %s",
        (id_sala,)
    )
    conn.commit()

    cursor.close()
    conn.close()

    return redirect("/salas")


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
