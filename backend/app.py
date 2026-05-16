from flask import Flask, send_from_directory, request, jsonify, session, redirect
from flask_socketio import SocketIO, join_room, emit
from werkzeug.security import generate_password_hash, check_password_hash
import requests
import mysql.connector
import os
import random
import string
from html import escape

app = Flask(__name__, static_folder="../front-end", static_url_path="")

app.secret_key = "nexy_secret_key"
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

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


def admin_logado():
    return usuario_logado() and session.get("tipo_usuario") == "admin"


def gerar_codigo():
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=6))


def h(valor):
    return escape(str(valor)) if valor is not None else ""


def contar_tabela(nome_tabela):
    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute(f"SELECT COUNT(*) AS total FROM {nome_tabela}")
        return cursor.fetchone()["total"]
    except Exception:
        return 0
    finally:
        cursor.close()
        conn.close()


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


@app.route("/config")
def config():
    base = NGROK_URL if NGROK_URL else request.host_url.rstrip("/")
    return jsonify({"base_url": base})


@app.route("/me")
def me():
    if not usuario_logado():
        return jsonify({"logado": False}), 401

    return jsonify({
        "logado": True,
        "usuario": session.get("usuario"),
        "id_usuario": session.get("id_usuario"),
        "tipo_usuario": session.get("tipo_usuario", "usuario")
    })


@app.route("/dashboard_stats")
def dashboard_stats():
    if not usuario_logado():
        return jsonify({"status": "erro", "msg": "Usuário não logado"}), 401

    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    try:
        # COUNT
        cursor.execute("SELECT COUNT(*) AS total FROM usuarios")
        total_usuarios = cursor.fetchone()["total"]

        cursor.execute("SELECT COUNT(*) AS total FROM salas")
        total_salas = cursor.fetchone()["total"]

        cursor.execute("SELECT COUNT(*) AS total FROM reunioes")
        total_reunioes = cursor.fetchone()["total"]

        cursor.execute("SELECT COUNT(*) AS total FROM mensagens")
        total_mensagens = cursor.fetchone()["total"]

        # SUM
        cursor.execute("""
            SELECT SUM(total_msg) AS soma_mensagens
            FROM (
                SELECT COUNT(*) AS total_msg
                FROM mensagens
                GROUP BY id_sala
            ) AS tabela
        """)
        soma_mensagens = cursor.fetchone()["soma_mensagens"]

        if soma_mensagens is None:
            soma_mensagens = 0

        # AVG
        cursor.execute("""
            SELECT AVG(total_msg) AS media_mensagens
            FROM (
                SELECT COUNT(*) AS total_msg
                FROM mensagens
                GROUP BY id_sala
            ) AS tabela
        """)
        media_mensagens = cursor.fetchone()["media_mensagens"]

        if media_mensagens is None:
            media_mensagens = 0

        return jsonify({
            "status": "ok",
            "total_usuarios": total_usuarios,
            "total_salas": total_salas,
            "total_reunioes": total_reunioes,
            "total_mensagens": total_mensagens,
            "soma_mensagens": soma_mensagens,
            "media_mensagens": round(media_mensagens, 2)
        })

    except Exception as e:
        return jsonify({"status": "erro", "msg": str(e)}), 500

    finally:
        cursor.close()
        conn.close()


@app.route("/register", methods=["POST"])
def register():
    data = request.json or {}

    nome = data.get("nome", "").strip()
    email = data.get("email", "").strip().lower()
    senha = data.get("senha", "").strip()

    if not nome or not email or not senha:
        return jsonify({"status": "erro", "msg": "Preencha todos os campos."})

    if "@" not in email or "." not in email:
        return jsonify({"status": "erro", "msg": "Informe um e-mail válido."})

    if len(senha) < 6:
        return jsonify({"status": "erro", "msg": "A senha deve ter pelo menos 6 caracteres."})

    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute(
            "SELECT id_usuario FROM usuarios WHERE LOWER(email) = %s",
            (email,)
        )
        email_existente = cursor.fetchone()

        if email_existente:
            return jsonify({"status": "erro", "msg": "Este e-mail já está cadastrado."})

        senha_hash = generate_password_hash(senha, method="pbkdf2:sha256")

        cursor.execute(
            """
            INSERT INTO usuarios (nome, email, senha)
            VALUES (%s, %s, %s)
            """,
            (nome, email, senha_hash)
        )

        conn.commit()
        return jsonify({"status": "ok"})

    except Exception as e:
        conn.rollback()
        return jsonify({"status": "erro", "msg": str(e)})

    finally:
        cursor.close()
        conn.close()


@app.route("/login", methods=["POST"])
def login():
    data = request.json or {}

    email = data.get("email", "").strip().lower()
    senha = data.get("senha", "").strip()

    if not email or not senha:
        return jsonify({"status": "erro", "msg": "Informe e-mail e senha."})

    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute(
            """
            SELECT id_usuario, nome, email, senha, tipo_usuario
            FROM usuarios
            WHERE LOWER(email) = %s
            """,
            (email,)
        )
        user = cursor.fetchone()

    except Exception:
        cursor.execute(
            """
            SELECT id_usuario, nome, email, senha
            FROM usuarios
            WHERE LOWER(email) = %s
            """,
            (email,)
        )
        user = cursor.fetchone()

    finally:
        cursor.close()
        conn.close()

    if user and check_password_hash(user["senha"], senha):
        tipo_usuario = user.get("tipo_usuario", "usuario")

        session["usuario"] = user["nome"]
        session["id_usuario"] = user["id_usuario"]
        session["tipo_usuario"] = tipo_usuario

        return jsonify({
            "status": "ok",
            "nome": user["nome"],
            "id": user["id_usuario"],
            "tipo_usuario": tipo_usuario
        })

    return jsonify({"status": "erro", "msg": "Login inválido."})


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/loginpage")


@app.route("/criar_reuniao")
def criar_reuniao():
    if not usuario_logado():
        return jsonify({"status": "erro", "msg": "Usuário não logado"}), 401

    codigo = gerar_codigo()
    base = NGROK_URL if NGROK_URL else request.host_url.rstrip("/")
    link = f"{base}/meeting/{codigo}"

    nome_sala = f"Sala {codigo}"
    id_criador = session.get("id_usuario")

    conn = get_db()
    cursor = conn.cursor()

    try:
        cursor.callproc(
            "criar_sala_com_log",
            (nome_sala, link, id_criador)
        )
        conn.commit()

    except Exception as e:
        conn.rollback()
        return jsonify({"status": "erro", "msg": str(e)}), 500

    finally:
        cursor.close()
        conn.close()

    return jsonify({
        "status": "ok",
        "codigo": codigo,
        "link": link
    })


@app.route("/usuarios")
def listar_usuarios():
    if not admin_logado():
        return "Acesso negado. Apenas administradores podem acessar esta área.", 403

    pagina = request.args.get("pagina", 1, type=int)
    limite = 10
    offset = (pagina - 1) * limite

    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT COUNT(*) AS total FROM usuarios")
    total = cursor.fetchone()["total"]

    try:
        cursor.execute(
            """
            SELECT id_usuario, nome, email, tipo_usuario, data_criacao
            FROM usuarios
            ORDER BY id_usuario DESC
            LIMIT %s OFFSET %s
            """,
            (limite, offset)
        )
    except Exception:
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
                <th>Tipo</th>
                <th>Data de criação</th>
                <th>Ações</th>
            </tr>
    """

    for u in usuarios:
        tipo = u.get("tipo_usuario", "usuario")

        html += f"""
            <tr>
                <td>{h(u['id_usuario'])}</td>
                <td>{h(u['nome'])}</td>
                <td>{h(u['email'])}</td>
                <td>{h(tipo)}</td>
                <td>{h(u.get('data_criacao', ''))}</td>
                <td>
                    <a class="btn" href="/usuarios/editar/{h(u['id_usuario'])}">Editar</a>
                    <a class="btn danger" href="/usuarios/excluir/{h(u['id_usuario'])}"
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
    if not admin_logado():
        return "Acesso negado. Apenas administradores podem acessar esta área.", 403

    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        email = request.form.get("email", "").strip().lower()
        tipo_usuario = request.form.get("tipo_usuario", "usuario").strip()

        if tipo_usuario not in ["admin", "usuario"]:
            tipo_usuario = "usuario"

        if not nome or not email:
            return "Nome e e-mail são obrigatórios. <br><a href='/usuarios'>Voltar</a>"

        cursor.execute(
            """
            SELECT id_usuario
            FROM usuarios
            WHERE LOWER(email) = %s AND id_usuario != %s
            """,
            (email, id_usuario)
        )

        email_existente = cursor.fetchone()

        if email_existente:
            cursor.close()
            conn.close()
            return "Este e-mail já está em uso por outro usuário. <br><a href='/usuarios'>Voltar</a>"

        try:
            cursor.execute(
                """
                UPDATE usuarios
                SET nome = %s, email = %s, tipo_usuario = %s
                WHERE id_usuario = %s
                """,
                (nome, email, tipo_usuario, id_usuario)
            )
        except Exception:
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

    try:
        cursor.execute(
            """
            SELECT id_usuario, nome, email, tipo_usuario
            FROM usuarios
            WHERE id_usuario = %s
            """,
            (id_usuario,)
        )
    except Exception:
        cursor.execute(
            """
            SELECT id_usuario, nome, email
            FROM usuarios
            WHERE id_usuario = %s
            """,
            (id_usuario,)
        )

    usuario = cursor.fetchone()

    cursor.close()
    conn.close()

    if not usuario:
        return "Usuário não encontrado."

    tipo_atual = usuario.get("tipo_usuario", "usuario")

    admin_selected = "selected" if tipo_atual == "admin" else ""
    usuario_selected = "selected" if tipo_atual == "usuario" else ""

    return f"""
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head>
        <meta charset="UTF-8">
        <title>Editar Usuário - Nexy</title>
        <style>
            body {{ background:#0f172a; color:white; font-family:Arial; padding:30px; }}
            input, select {{ width:100%; max-width:400px; padding:10px; margin:8px 0; border-radius:6px; border:none; }}
            button, a {{ padding:10px 14px; background:#3b82f6; color:white; border:none; border-radius:6px; text-decoration:none; cursor:pointer; }}
        </style>
    </head>
    <body>
        <h1>Editar Usuário</h1>

        <form method="POST">
            <label>Nome:</label><br>
            <input type="text" name="nome" value="{h(usuario['nome'])}" required><br>

            <label>Email:</label><br>
            <input type="email" name="email" value="{h(usuario['email'])}" required><br>

            <label>Tipo de usuário:</label><br>
            <select name="tipo_usuario">
                <option value="usuario" {usuario_selected}>Usuário comum</option>
                <option value="admin" {admin_selected}>Admin</option>
            </select><br><br>

            <button type="submit">Salvar alterações</button>
            <a href="/usuarios">Cancelar</a>
        </form>
    </body>
    </html>
    """


@app.route("/usuarios/excluir/<int:id_usuario>")
def excluir_usuario(id_usuario):
    if not admin_logado():
        return "Acesso negado. Apenas administradores podem acessar esta área.", 403

    if id_usuario == session.get("id_usuario"):
        return "Você não pode excluir o próprio usuário enquanto está logado. <br><a href='/usuarios'>Voltar</a>"

    conn = get_db()
    cursor = conn.cursor()

    try:
        cursor.execute(
            "DELETE FROM usuarios WHERE id_usuario = %s",
            (id_usuario,)
        )
        conn.commit()

    except Exception as e:
        conn.rollback()
        return f"Erro ao excluir usuário: {h(e)} <br><a href='/usuarios'>Voltar</a>"

    finally:
        cursor.close()
        conn.close()

    return redirect("/usuarios")


@app.route("/salas")
def listar_salas():
    if not admin_logado():
        return "Acesso negado. Apenas administradores podem acessar esta área.", 403

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
                <td>{h(s['id_sala'])}</td>
                <td>{h(s['nome_sala'])}</td>
                <td><a href="{h(s['link'])}" target="_blank">Abrir link</a></td>
                <td>{h(s['id_criador'])}</td>
                <td>
                    <a class="btn" href="/salas/editar/{h(s['id_sala'])}">Editar</a>
                    <a class="btn danger" href="/salas/excluir/{h(s['id_sala'])}"
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
    if not admin_logado():
        return "Acesso negado. Apenas administradores podem acessar esta área.", 403

    if request.method == "POST":
        nome_sala = request.form.get("nome_sala", "").strip()

        if not nome_sala:
            return "Nome da sala é obrigatório. <br><a href='/salas/nova'>Voltar</a>"

        conn = get_db()
        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            "SELECT id_sala FROM salas WHERE LOWER(nome_sala) = %s",
            (nome_sala.lower(),)
        )

        sala_existente = cursor.fetchone()

        if sala_existente:
            cursor.close()
            conn.close()
            return "Já existe uma sala com esse nome. <br><a href='/salas/nova'>Voltar</a>"

        codigo = gerar_codigo()
        base = NGROK_URL if NGROK_URL else request.host_url.rstrip("/")
        link = f"{base}/meeting/{codigo}"
        id_criador = session.get("id_usuario")

        try:
            cursor.execute(
                """
                INSERT INTO salas (nome_sala, link, id_criador)
                VALUES (%s, %s, %s)
                """,
                (nome_sala, link, id_criador)
            )
            conn.commit()

        except Exception as e:
            conn.rollback()
            return f"Erro ao criar sala: {h(e)} <br><a href='/salas/nova'>Voltar</a>"

        finally:
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
    if not admin_logado():
        return "Acesso negado. Apenas administradores podem acessar esta área.", 403

    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    if request.method == "POST":
        nome_sala = request.form.get("nome_sala", "").strip()
        link = request.form.get("link", "").strip()

        if not nome_sala or not link:
            return "Nome da sala e link são obrigatórios. <br><a href='/salas'>Voltar</a>"

        cursor.execute(
            """
            SELECT id_sala
            FROM salas
            WHERE LOWER(nome_sala) = %s AND id_sala != %s
            """,
            (nome_sala.lower(), id_sala)
        )

        sala_existente = cursor.fetchone()

        if sala_existente:
            cursor.close()
            conn.close()
            return "Já existe outra sala com esse nome. <br><a href='/salas'>Voltar</a>"

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
            <input type="text" name="nome_sala" value="{h(sala['nome_sala'])}" required><br>

            <label>Link:</label><br>
            <input type="text" name="link" value="{h(sala['link'])}" required><br><br>

            <button type="submit">Salvar alterações</button>
            <a href="/salas">Cancelar</a>
        </form>
    </body>
    </html>
    """


@app.route("/salas/excluir/<int:id_sala>")
def excluir_sala(id_sala):
    if not admin_logado():
        return "Acesso negado. Apenas administradores podem acessar esta área.", 403

    conn = get_db()
    cursor = conn.cursor()

    try:
        cursor.execute(
            "DELETE FROM salas WHERE id_sala = %s",
            (id_sala,)
        )
        conn.commit()

    except Exception as e:
        conn.rollback()
        return f"Erro ao excluir sala: {h(e)} <br><a href='/salas'>Voltar</a>"

    finally:
        cursor.close()
        conn.close()

    return redirect("/salas")


@app.route("/relatorio_reunioes")
def relatorio_reunioes():
    if not admin_logado():
        return "Acesso negado. Apenas administradores podem acessar esta área.", 403

    data_inicio = request.args.get("data_inicio", "")
    data_fim = request.args.get("data_fim", "")
    status = request.args.get("status", "")
    sala = request.args.get("sala", "")

    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    sql = """
        SELECT 
            r.id_reuniao,
            s.nome_sala,
            s.link,
            r.data_inicio,
            r.data_fim,
            CASE
                WHEN r.data_fim IS NULL THEN 'Em andamento'
                ELSE 'Finalizada'
            END AS status
        FROM reunioes r
        LEFT JOIN salas s ON r.id_sala = s.id_sala
        WHERE 1 = 1
    """

    params = []

    if data_inicio:
        sql += " AND DATE(r.data_inicio) >= %s"
        params.append(data_inicio)

    if data_fim:
        sql += " AND DATE(r.data_inicio) <= %s"
        params.append(data_fim)

    if status == "em_andamento":
        sql += " AND r.data_fim IS NULL"

    if status == "finalizada":
        sql += " AND r.data_fim IS NOT NULL"

    if sala:
        sql += " AND s.nome_sala LIKE %s"
        params.append(f"%{sala}%")

    sql += " ORDER BY r.data_inicio DESC"

    cursor.execute(sql, params)
    reunioes = cursor.fetchall()

    cursor.close()
    conn.close()

    html = f"""
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head>
        <meta charset="UTF-8">
        <title>Relatório de Reuniões - Nexy</title>

        <style>
            body {{ background:#0f172a; color:white; font-family:Arial; padding:30px; }}
            input, select {{ padding:10px; border-radius:6px; border:none; margin:5px; }}
            button, a {{ padding:10px 14px; background:#3b82f6; color:white; border:none; border-radius:6px; text-decoration:none; cursor:pointer; }}
            table {{ width:100%; border-collapse:collapse; background:#1e293b; margin-top:20px; }}
            th, td {{ padding:12px; border-bottom:1px solid #334155; text-align:left; }}
            th {{ background:#020617; }}
            .card {{ background:#1e293b; padding:20px; border-radius:10px; margin-bottom:20px; }}
        </style>
    </head>

    <body>
        <h1>Relatório de Reuniões</h1>

        <a href="/dashboard">Voltar ao Dashboard</a>

        <div class="card" style="margin-top:20px;">
            <form method="GET">
                <label>Data inicial:</label>
                <input type="date" name="data_inicio" value="{h(data_inicio)}">

                <label>Data final:</label>
                <input type="date" name="data_fim" value="{h(data_fim)}">

                <label>Status:</label>
                <select name="status">
                    <option value="">Todos</option>
                    <option value="em_andamento" {"selected" if status == "em_andamento" else ""}>Em andamento</option>
                    <option value="finalizada" {"selected" if status == "finalizada" else ""}>Finalizada</option>
                </select>

                <label>Sala:</label>
                <input type="text" name="sala" placeholder="Nome da sala" value="{h(sala)}">

                <button type="submit">Filtrar</button>
            </form>
        </div>

        <table>
            <tr>
                <th>ID</th>
                <th>Sala</th>
                <th>Início</th>
                <th>Fim</th>
                <th>Status</th>
                <th>Link</th>
            </tr>
    """

    if not reunioes:
        html += """
            <tr>
                <td colspan="6">Nenhuma reunião encontrada com os filtros informados.</td>
            </tr>
        """
    else:
        for r in reunioes:
            html += f"""
                <tr>
                    <td>{h(r['id_reuniao'])}</td>
                    <td>{h(r['nome_sala'])}</td>
                    <td>{h(r['data_inicio'])}</td>
                    <td>{h(r['data_fim'])}</td>
                    <td>{h(r['status'])}</td>
                    <td><a href="{h(r['link'])}" target="_blank">Abrir</a></td>
                </tr>
            """

    html += """
        </table>
    </body>
    </html>
    """

    return html


@app.route("/chat", methods=["POST"])
def chat_api():
    try:
        data = request.json or {}
        msg = data.get("msg", "").strip().lower()

        msg = msg.replace("oq", "o que")
        msg = msg.replace("q ", "que ")
        msg = msg.replace("vc", "você")

        respostas_fixas = {
            "webrtc": "WebRTC é uma tecnologia que permite comunicação em tempo real com áudio, vídeo e dados diretamente no navegador.",
            "instagram": "Instagram é uma rede social onde as pessoas compartilham fotos, vídeos e interagem com outros usuários.",
            "inteligencia artificial": "Inteligência Artificial é uma área da computação que permite que sistemas simulem tarefas inteligentes.",
            "inteligência artificial": "Inteligência Artificial é uma área da computação que permite que sistemas simulem tarefas inteligentes.",
            "nexy": "Nexy é uma plataforma de videoconferência com inteligência artificial integrada."
        }

        for chave in respostas_fixas:
            if chave in msg:
                return jsonify({"resposta": respostas_fixas[chave]})

        r = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": "phi",
                "prompt": f"Responda em português do Brasil, de forma simples e direta: {msg}",
                "stream": False
            },
            timeout=30
        )

        resposta = r.json().get("response", "").strip()

        palavras_ingles = [" is ", " are ", " the ", " and ", "with", "this", "that"]

        if any(p in resposta.lower() for p in palavras_ingles):
            resposta = "Não consegui responder corretamente em português. Tente reformular a pergunta."

        lixo = ["Pergunta", "Resposta", "Assistant", "Hello"]

        for palavra in lixo:
            resposta = resposta.replace(palavra, "")

        if len(resposta) > 300:
            resposta = resposta[:300] + "..."

        return jsonify({"resposta": resposta})

    except Exception as e:
        print("ERRO CHAT:", e)
        return jsonify({"resposta": "Erro no servidor de IA"})


@socketio.on("join")
def on_join(data):
    room = data.get("room")
    nome = data.get("nome", "Usuário")

    if not room:
        return

    join_room(room)

    emit("user_joined", {
        "id": request.sid,
        "nome": nome
    }, room=room)

    try:
        users = list(socketio.server.manager.rooms["/"].get(room, []))
    except Exception:
        users = []

    emit("all_users", {
        "users": users
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
    room = data.get("room")

    if not room:
        return

    emit("chat", data, room=room, include_self=False)


@socketio.on("disconnect")
def handle_disconnect():
    emit("user-disconnected", request.sid, broadcast=True)


if __name__ == "__main__":
    socketio.run(app, port=5000, debug=True)