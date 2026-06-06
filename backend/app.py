from flask import Flask, send_from_directory, request, jsonify, session, redirect
from flask_socketio import SocketIO, join_room, emit
from werkzeug.security import generate_password_hash, check_password_hash
import requests
import mysql.connector
import os
from dotenv import load_dotenv
import random
import string
from html import escape
import socket

try:
 from pyngrok import ngrok
except ImportError:
    ngrok = None

app = Flask(__name__, static_folder="../front-end", static_url_path="")

app.secret_key = "nexy_secret_key"
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

socketio = SocketIO(app, cors_allowed_origins="*")

load_dotenv()

NGROK_URL = os.getenv("NGROK_URL")
NGROK_AUTHTOKEN = os.getenv("NGROK_AUTHTOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")


def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


def get_base_url():
    if NGROK_URL:
        return NGROK_URL.rstrip("/")

    base = request.host_url.rstrip("/")
    if base.startswith("http://127.0.0.1") or base.startswith("http://localhost"):
        local_ip = get_local_ip()
        return base.replace("127.0.0.1", local_ip).replace("localhost", local_ip)

    return base


def start_ngrok():
    print(f"[ngrok] start_ngrok called. NGROK_URL set={bool(NGROK_URL)}, NGROK_AUTHTOKEN set={bool(NGROK_AUTHTOKEN)}")

    if not ngrok:
        print("[ngrok] pyngrok não está instalado. Instale pyngrok no requirements.txt.")
        return None

    if not NGROK_AUTHTOKEN:
        print("[ngrok] NGROK_AUTHTOKEN não está configurado.")
        return None

    try:
        ngrok.set_auth_token(NGROK_AUTHTOKEN)
        public_url = ngrok.connect(5000, bind_tls=True).public_url
        return public_url
    except Exception as e:
        print(f"[ngrok] erro ao iniciar ngrok: {e}")
        return None


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


# ===== Tema visual compartilhado das páginas administrativas =====
ADMIN_CSS = """
:root{
  --bg:#0b1120; --surface:#16213a; --surface-2:#1c2742;
  --border:rgba(148,163,184,0.14); --primary:#3b82f6; --primary-2:#2563eb;
  --text:#e8eefc; --muted:#94a3b8; --danger:#ef4444;
}
*{box-sizing:border-box;}
body{
  margin:0; font-family:'Segoe UI',Tahoma,Geneva,Verdana,sans-serif;
  background:
    radial-gradient(circle at 85% -10%, rgba(56,189,248,0.10), transparent 35%),
    radial-gradient(circle at 0% 100%, rgba(124,58,237,0.10), transparent 35%),
    linear-gradient(180deg,#08101f 0%, #0b1120 60%);
  color:var(--text); min-height:100vh;
}
a{color:#60a5fa; text-decoration:none;}
.page{max-width:1100px; margin:0 auto; padding:28px 26px 60px;}
.page.center{min-height:100vh; display:flex; flex-direction:column; align-items:center; justify-content:center;}
.page.center .page-head{justify-content:center;}
.page.center .form-card{width:100%;}
.page-head{display:flex; align-items:center; gap:18px; margin-bottom:26px;}
.page-head .logo{height:46px; width:auto;}
.page-head h1{font-size:24px; font-weight:700; letter-spacing:.3px; margin:0;}

.toolbar{display:flex; flex-wrap:wrap; gap:10px; margin-bottom:22px;}

.btn{
  display:inline-flex; align-items:center; gap:8px;
  padding:10px 16px; border-radius:10px; font-size:14px; font-weight:600;
  border:1px solid var(--border); background:var(--surface-2); color:var(--text);
  cursor:pointer; transition:all .2s ease; text-decoration:none;
}
.btn:hover{border-color:rgba(96,165,250,.5); background:rgba(59,130,246,.14); transform:translateY(-1px);}
.btn.primary{background:linear-gradient(135deg,var(--primary),var(--primary-2)); border-color:transparent; box-shadow:0 8px 22px rgba(59,130,246,.3);}
.btn.primary:hover{background:linear-gradient(135deg,#2563eb,#1d4ed8);}
.btn.danger{background:rgba(239,68,68,.16); border-color:rgba(239,68,68,.4); color:#fca5a5;}
.btn.danger:hover{background:rgba(239,68,68,.28); border-color:rgba(239,68,68,.6); color:#fecaca;}
.btn.ghost{background:transparent;}
.btn.sm{padding:7px 12px; font-size:13px;}

.panel{background:var(--surface); border:1px solid var(--border); border-radius:16px; overflow:hidden; box-shadow:0 12px 34px rgba(2,6,23,.4);}
.table-wrap{width:100%; overflow-x:auto;}
table{width:100%; border-collapse:collapse; min-width:640px;}
thead th{
  text-align:left; padding:14px 18px; font-size:12px; text-transform:uppercase;
  letter-spacing:.08em; color:var(--muted); background:rgba(2,6,23,.5);
  border-bottom:1px solid var(--border); font-weight:700; white-space:nowrap;
}
tbody td{padding:14px 18px; border-bottom:1px solid var(--border); font-size:14px; vertical-align:middle;}
tbody tr{transition:background .18s ease;}
tbody tr:hover{background:rgba(59,130,246,.07);}
tbody tr:last-child td{border-bottom:none;}
.id-cell{color:var(--muted); font-variant-numeric:tabular-nums;}
.actions{display:flex; gap:8px; flex-wrap:wrap;}

.badge{display:inline-block; padding:3px 11px; border-radius:999px; font-size:12px; font-weight:600; border:1px solid transparent; text-transform:capitalize;}
.badge.admin{background:rgba(124,58,237,.2); color:#c4b5fd; border-color:rgba(124,58,237,.4);}
.badge.user{background:rgba(37,99,235,.2); color:#93c5fd; border-color:rgba(96,165,250,.3);}
.badge.on{background:rgba(34,197,94,.18); color:#4ade80; border-color:rgba(34,197,94,.4);}
.badge.off{background:rgba(148,163,184,.18); color:#cbd5e1; border-color:rgba(148,163,184,.35);}

.empty{padding:38px; text-align:center; color:var(--muted); font-size:14px;}

.pagination{display:flex; align-items:center; gap:8px; margin-top:20px; flex-wrap:wrap;}
.pagination .lbl{color:var(--muted); font-size:13px; margin-right:4px;}
.pagination a{
  display:inline-grid; place-items:center; min-width:38px; height:38px; padding:0 10px;
  border-radius:10px; border:1px solid var(--border); background:var(--surface);
  color:var(--text); font-weight:600; transition:all .2s ease;
}
.pagination a:hover{border-color:rgba(96,165,250,.5); background:rgba(59,130,246,.14); transform:translateY(-1px);}
.pagination a.active{background:linear-gradient(135deg,var(--primary),var(--primary-2)); border-color:transparent; box-shadow:0 6px 16px rgba(59,130,246,.3);}

.form-card{background:var(--surface); border:1px solid var(--border); border-radius:16px; padding:26px; max-width:560px; box-shadow:0 12px 34px rgba(2,6,23,.4);}
.filters{display:flex; flex-wrap:wrap; gap:14px; align-items:flex-end; background:var(--surface); border:1px solid var(--border); border-radius:16px; padding:20px; margin-bottom:22px; box-shadow:0 12px 34px rgba(2,6,23,.4);}
.field{display:flex; flex-direction:column; gap:6px;}
.field label{font-size:12.5px; color:var(--muted); font-weight:600;}
input, select{
  padding:11px 13px; border-radius:10px; border:1px solid var(--border);
  background:rgba(255,255,255,.06); color:var(--text); font-size:14px; outline:none;
  transition:border-color .2s ease, box-shadow .2s ease;
}
input::placeholder{color:rgba(148,163,184,.7);}
input:focus, select:focus{border-color:#60a5fa; box-shadow:0 0 0 3px rgba(59,130,246,.18);}
select{appearance:none; -webkit-appearance:none; cursor:pointer;
  background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%2394a3b8' stroke-width='3'%3E%3Cpath d='M6 9l6 6 6-6'/%3E%3C/svg%3E");
  background-repeat:no-repeat; background-position:right 12px center; padding-right:34px;}
select option{background:#1c2742; color:#e8eefc;}
.form-card .field{margin-bottom:16px;}
.form-card input, .form-card select{width:100%;}
.form-actions{display:flex; gap:10px; margin-top:8px;}
.link-cell a{display:inline-flex; align-items:center; gap:6px;}
@media(max-width:600px){ .page{padding:18px 14px 50px;} .page-head h1{font-size:20px;} .page-head .logo{height:38px;} }
"""


def admin_page(title, inner, center=False):
    """Envolve o conteúdo numa página administrativa com tema e logo no topo."""
    page_cls = "page center" if center else "page"
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title} - Nexy</title>
<style>{ADMIN_CSS}</style>
</head>
<body>
<div class="{page_cls}">
  <header class="page-head">
    <img class="logo" src="/img/nexy-logo.svg" alt="Nexy">
    <h1>{title}</h1>
  </header>
  {inner}
</div>
</body>
</html>"""


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
    return send_from_directory(app.static_folder, "meeting.html")


@app.route("/sobre")
def sobre():
    return send_from_directory(app.static_folder, "sobre.html")


@app.route("/config")
def config():
    base = get_base_url()
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
    base = get_base_url()
    link = f"{base}/meeting/{codigo}"

    nome_informado = request.args.get("nome", "").strip()
    nome_sala = nome_informado[:60] if nome_informado else f"Sala {codigo}"
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
        "link": link,
        "nome": nome_sala
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

    rows = ""
    for u in usuarios:
        tipo = u.get("tipo_usuario", "usuario")
        badge = "admin" if tipo == "admin" else "user"
        rows += f"""
            <tr>
                <td class="id-cell">#{h(u['id_usuario'])}</td>
                <td>{h(u['nome'])}</td>
                <td>{h(u['email'])}</td>
                <td><span class="badge {badge}">{h(tipo)}</span></td>
                <td>{h(u.get('data_criacao', '') or '—')}</td>
                <td><div class="actions">
                    <a class="btn sm" href="/usuarios/editar/{h(u['id_usuario'])}">✏️ Editar</a>
                    <a class="btn sm danger" href="/usuarios/excluir/{h(u['id_usuario'])}"
                       onclick="return confirm('Tem certeza que deseja excluir este usuário?')">🗑️ Excluir</a>
                </div></td>
            </tr>"""

    if not usuarios:
        rows = '<tr><td colspan="6" class="empty">Nenhum usuário cadastrado.</td></tr>'

    paginacao = ""
    if total_paginas > 1:
        links = ""
        for p in range(1, total_paginas + 1):
            cls = "active" if p == pagina else ""
            links += f'<a class="{cls}" href="/usuarios?pagina={p}">{p}</a>'
        paginacao = f'<div class="pagination"><span class="lbl">Páginas:</span>{links}</div>'

    inner = f"""
    <div class="toolbar">
      <a class="btn" href="/dashboard">← Voltar ao Dashboard</a>
    </div>
    <div class="panel"><div class="table-wrap">
      <table>
        <thead><tr>
          <th>ID</th><th>Nome</th><th>Email</th><th>Tipo</th><th>Criado em</th><th>Ações</th>
        </tr></thead>
        <tbody>{rows}
        </tbody>
      </table>
    </div></div>
    {paginacao}
    """

    return admin_page("Gerenciar Usuários", inner)


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

    inner = f"""
    <div class="form-card">
      <form method="POST">
        <div class="field">
          <label>Nome</label>
          <input type="text" name="nome" value="{h(usuario['nome'])}" required>
        </div>
        <div class="field">
          <label>E-mail</label>
          <input type="email" name="email" value="{h(usuario['email'])}" required>
        </div>
        <div class="field">
          <label>Tipo de usuário</label>
          <select name="tipo_usuario">
            <option value="usuario" {usuario_selected}>Usuário comum</option>
            <option value="admin" {admin_selected}>Admin</option>
          </select>
        </div>
        <div class="form-actions">
          <button class="btn primary" type="submit">💾 Salvar alterações</button>
          <a class="btn" href="/usuarios">Cancelar</a>
        </div>
      </form>
    </div>
    """
    return admin_page("Editar Usuário", inner, center=True)


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

    rows = ""
    for s in salas:
        rows += f"""
            <tr>
                <td class="id-cell">#{h(s['id_sala'])}</td>
                <td>{h(s['nome_sala'])}</td>
                <td class="link-cell"><a href="{h(s['link'])}" target="_blank">🔗 Abrir link</a></td>
                <td class="id-cell">{h(s['id_criador'])}</td>
                <td><div class="actions">
                    <a class="btn sm" href="/salas/editar/{h(s['id_sala'])}">✏️ Editar</a>
                    <a class="btn sm danger" href="/salas/excluir/{h(s['id_sala'])}"
                       onclick="return confirm('Tem certeza que deseja excluir esta sala?')">🗑️ Excluir</a>
                </div></td>
            </tr>"""

    if not salas:
        rows = '<tr><td colspan="5" class="empty">Nenhuma sala cadastrada.</td></tr>'

    paginacao = ""
    if total_paginas > 1:
        links = ""
        for p in range(1, total_paginas + 1):
            cls = "active" if p == pagina else ""
            links += f'<a class="{cls}" href="/salas?pagina={p}">{p}</a>'
        paginacao = f'<div class="pagination"><span class="lbl">Páginas:</span>{links}</div>'

    inner = f"""
    <div class="toolbar">
      <a class="btn" href="/dashboard">← Voltar ao Dashboard</a>
      <a class="btn primary" href="/salas/nova">＋ Nova Sala</a>
    </div>
    <div class="panel"><div class="table-wrap">
      <table>
        <thead><tr>
          <th>ID</th><th>Nome da sala</th><th>Link</th><th>Criador</th><th>Ações</th>
        </tr></thead>
        <tbody>{rows}
        </tbody>
      </table>
    </div></div>
    {paginacao}
    """

    return admin_page("Gerenciar Salas", inner)


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
        base = get_base_url()
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

    inner = """
    <div class="form-card">
      <form method="POST">
        <div class="field">
          <label>Nome da sala</label>
          <input type="text" name="nome_sala" placeholder="Ex.: Reunião de equipe" required>
        </div>
        <div class="form-actions">
          <button class="btn primary" type="submit">＋ Criar sala</button>
          <a class="btn" href="/salas">Cancelar</a>
        </div>
      </form>
    </div>
    """
    return admin_page("Nova Sala", inner, center=True)


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

    inner = f"""
    <div class="form-card">
      <form method="POST">
        <div class="field">
          <label>Nome da sala</label>
          <input type="text" name="nome_sala" value="{h(sala['nome_sala'])}" required>
        </div>
        <div class="field">
          <label>Link</label>
          <input type="text" name="link" value="{h(sala['link'])}" required>
        </div>
        <div class="form-actions">
          <button class="btn primary" type="submit">💾 Salvar alterações</button>
          <a class="btn" href="/salas">Cancelar</a>
        </div>
      </form>
    </div>
    """
    return admin_page("Editar Sala", inner, center=True)


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

    rows = ""
    if not reunioes:
        rows = '<tr><td colspan="6" class="empty">Nenhuma reunião encontrada com os filtros informados.</td></tr>'
    else:
        for r in reunioes:
            st = r["status"]
            badge = "on" if st == "Em andamento" else "off"
            rows += f"""
                <tr>
                    <td class="id-cell">#{h(r['id_reuniao'])}</td>
                    <td>{h(r['nome_sala'] or '—')}</td>
                    <td>{h(r['data_inicio'])}</td>
                    <td>{h(r['data_fim'] or '—')}</td>
                    <td><span class="badge {badge}">{h(st)}</span></td>
                    <td class="link-cell"><a href="{h(r['link'])}" target="_blank">🔗 Abrir</a></td>
                </tr>"""

    sel_and = "selected" if status == "em_andamento" else ""
    sel_fin = "selected" if status == "finalizada" else ""

    inner = f"""
    <div class="toolbar">
      <a class="btn" href="/dashboard">← Voltar ao Dashboard</a>
    </div>
    <form class="filters" method="GET">
      <div class="field">
        <label>Data inicial</label>
        <input type="date" name="data_inicio" value="{h(data_inicio)}">
      </div>
      <div class="field">
        <label>Data final</label>
        <input type="date" name="data_fim" value="{h(data_fim)}">
      </div>
      <div class="field">
        <label>Status</label>
        <select name="status">
          <option value="">Todos</option>
          <option value="em_andamento" {sel_and}>Em andamento</option>
          <option value="finalizada" {sel_fin}>Finalizada</option>
        </select>
      </div>
      <div class="field">
        <label>Sala</label>
        <input type="text" name="sala" placeholder="Nome da sala" value="{h(sala)}">
      </div>
      <button class="btn primary" type="submit">🔍 Filtrar</button>
    </form>
    <div class="panel"><div class="table-wrap">
      <table>
        <thead><tr>
          <th>ID</th><th>Sala</th><th>Início</th><th>Fim</th><th>Status</th><th>Link</th>
        </tr></thead>
        <tbody>{rows}
        </tbody>
      </table>
    </div></div>
    """

    return admin_page("Relatório de Reuniões", inner)


@app.route("/chat", methods=["POST"])
def chat_api():
    try:
        data = request.json or {}
        msg = data.get("msg", "").strip()

        if not msg:
            return jsonify({"resposta": "Digite uma pergunta."})

        respostas_fixas = {
            "webrtc": "WebRTC é uma tecnologia que permite comunicação em tempo real com áudio, vídeo e dados diretamente no navegador.",
            "instagram": "Instagram é uma rede social onde as pessoas compartilham fotos, vídeos e interagem com outros usuários.",
            "inteligencia artificial": "Inteligência Artificial é uma área da computação que permite que sistemas simulem tarefas inteligentes.",
            "inteligência artificial": "Inteligência Artificial é uma área da computação que permite que sistemas simulem tarefas inteligentes.",
            "nexy": "Nexy é uma plataforma de videoconferência com inteligência artificial integrada."
        }

        msg_normalizada = msg.lower()
        msg_normalizada = msg_normalizada.replace("oq", "o que")
        msg_normalizada = msg_normalizada.replace("q ", "que ")
        msg_normalizada = msg_normalizada.replace("vc", "você")

        for chave in respostas_fixas:
            if chave in msg_normalizada:
                return jsonify({"resposta": respostas_fixas[chave]})

        if not GROQ_API_KEY:
            return jsonify({
                "resposta": "Chave da Groq não configurada. Crie o arquivo .env com GROQ_API_KEY=sua_chave."
            })

        url = "https://api.groq.com/openai/v1/chat/completions"

        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": "llama-3.1-8b-instant",
            "messages": [
                {
                    "role": "system",
                    "content": "Você é a IA da plataforma NEXY. Responda sempre em português do Brasil, de forma simples, direta e útil. Evite respostas longas."
                },
                {
                    "role": "user",
                    "content": msg
                }
            ],
            "temperature": 0.4,
            "max_tokens": 250
        }

        r = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=20
        )

        if r.status_code != 200:
            print("ERRO GROQ:", r.status_code, r.text)
            return jsonify({
                "resposta": "Não consegui acessar a IA agora. Verifique a chave da Groq."
            })

        resposta = r.json()["choices"][0]["message"]["content"].strip()

        return jsonify({"resposta": resposta})

    except Exception as e:
        print("ERRO CHAT:", e)
        return jsonify({"resposta": "Erro no servidor de IA."})

# nome do participante associado a cada socket (sid)
nomes_por_sid = {}


@socketio.on("join")
def on_join(data):
    room = data.get("room")
    nome = data.get("nome", "Usuário")

    if not room:
        return

    join_room(room)

    # guarda o nome deste participante
    nomes_por_sid[request.sid] = nome

    emit("user_joined", {
        "id": request.sid,
        "nome": nome
    }, room=room)

    try:
        users = list(socketio.server.manager.rooms["/"].get(room, []))
    except Exception:
        users = []

    # envia a lista de participantes já com os nomes
    usuarios_info = [
        {"id": uid, "nome": nomes_por_sid.get(uid, "Usuário")}
        for uid in users
    ]

    emit("all_users", {
        "users": users,
        "usuarios": usuarios_info
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
    rooms = socketio.server.rooms(request.sid)

    for room in rooms:
        if room != request.sid:
            emit("user-disconnected", request.sid, room=room)

    nomes_por_sid.pop(request.sid, None)


if __name__ == "__main__":
    if not NGROK_URL and NGROK_AUTHTOKEN:
        public_url = start_ngrok()
        if public_url:
            NGROK_URL = public_url
            print(f"[ngrok] public url: {NGROK_URL}")

    socketio.run(app, host="0.0.0.0", port=5000, debug=False, allow_unsafe_werkzeug=True)