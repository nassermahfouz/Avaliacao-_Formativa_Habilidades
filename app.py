
from flask import Flask, render_template, request, redirect, session, send_file
import sqlite3, os, csv, json
from datetime import datetime

app = Flask(__name__)
app.secret_key = "etapa_config"

DB_FILE = "notas.db"
CONFIG_FILE = "config.json"

def carregar_config():
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def init_db():
    if not os.path.exists(DB_FILE):
        with sqlite3.connect(DB_FILE) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS notas (
                    id INTEGER PRIMARY KEY,
                    aluno TEXT,
                    professor TEXT,
                    nota REAL,
                    datahora TEXT
                )
            ''')

init_db()

@app.route("/login", methods=["GET", "POST"])
def login():
    cfg = carregar_config()
    erro = None
    if request.method == "POST":
        nome = request.form.get("professor")
        senha = request.form.get("senha")
        if nome in cfg["usuarios"] and senha == cfg["usuarios"][nome]["senha"]:
            session["usuario"] = nome
            return redirect("/")
        else:
            erro = "Nome ou senha inválidos."
    return render_template("login.html", professores=list(cfg["usuarios"].keys()), erro=erro)

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

@app.route("/alterar-senha", methods=["GET", "POST"])
def alterar_senha():
    if "usuario" not in session:
        return redirect("/login")
    erro = sucesso = None
    cfg = carregar_config()
    usuario = session["usuario"]
    if request.method == "POST":
        atual = request.form["senha_atual"]
        nova = request.form["nova_senha"]
        confirma = request.form["confirmar_senha"]
        if atual != cfg["usuarios"][usuario]["senha"]:
            erro = "Senha atual incorreta."
        elif nova != confirma:
            erro = "Nova senha e confirmação não coincidem."
        else:
            cfg["usuarios"][usuario]["senha"] = nova
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=2)
            sucesso = "Senha alterada com sucesso!"
    return render_template("alterar_senha.html", titulo=cfg["titulo"], erro=erro, sucesso=sucesso)

@app.route("/", methods=["GET", "POST"])
def index():
    if "usuario" not in session:
        return redirect("/login")
    cfg = carregar_config()
    usuario = session["usuario"]
    resultado = None
    if request.method == "POST":
        aluno = request.form.get("aluno")
        nota = request.form.get("nota")
        try:
            nota = float(nota)
            if 0 <= nota <= 10:
                with sqlite3.connect(DB_FILE) as conn:
                    conn.execute("INSERT INTO notas (aluno, professor, nota, datahora) VALUES (?, ?, ?, ?)",
                                 (aluno, usuario, nota, datetime.now().isoformat()))
                resultado = f"Nota registrada com sucesso: {aluno} - {nota}"
            else:
                resultado = "A nota deve estar entre 0 e 10."
        except:
            resultado = "Nota inválida."
    return render_template("index.html", titulo=cfg["titulo"], alunos=cfg["alunos"],
                           usuario=usuario, acesso=cfg["usuarios"][usuario]["acesso_relatorio"],
                           resultado=resultado)

@app.route("/relatorio", methods=["GET", "POST"])
def relatorio():
    if "usuario" not in session:
        return redirect("/login")
    cfg = carregar_config()
    usuario = session["usuario"]
    if not cfg["usuarios"][usuario]["acesso_relatorio"]:
        return redirect("/")
    registros = []
    if request.method == "POST":
        aluno = request.form.get("aluno")
        professor = request.form.get("professor")
        data_ini = request.form.get("data_ini")
        data_fim = request.form.get("data_fim")
        query = "SELECT id, aluno, professor, nota, datahora FROM notas WHERE 1=1"
        params = []
        if aluno:
            query += " AND aluno = ?"
            params.append(aluno)
        if professor:
            query += " AND professor = ?"
            params.append(professor)
        if data_ini:
            query += " AND datahora >= ?"
            params.append(data_ini)
        if data_fim:
            query += " AND datahora <= ?"
            params.append(data_fim + 'T23:59:59')
        with sqlite3.connect(DB_FILE) as conn:
            registros = conn.execute(query, params).fetchall()
            with open("export_notas.csv", "w", newline="", encoding="utf-8") as f:
                csv.writer(f).writerows([["Aluno", "Professor", "Nota", "DataHora"]] + registros)
    return render_template("relatorio.html", titulo=cfg["titulo"], alunos=cfg["alunos"],
                           professores=list(cfg["usuarios"].keys()), registros=registros)

@app.route("/editar-nota/<int:nota_id>", methods=["GET", "POST"])
def editar_nota(nota_id):
    if "usuario" not in session:
        return redirect("/login")
    cfg = carregar_config()
    usuario = session["usuario"]
    if not cfg["usuarios"][usuario]["acesso_relatorio"]:
        return redirect("/")
    erro = sucesso = None
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        nota_info = cursor.execute("SELECT aluno, professor, nota FROM notas WHERE id=?", (nota_id,)).fetchone()
        if not nota_info:
            return "Nota não encontrada."
        aluno, professor, nota_atual = nota_info
        if request.method == "POST":
            try:
                nova = float(request.form["nova_nota"])
                if 0 <= nova <= 10:
                    cursor.execute("UPDATE notas SET nota=? WHERE id=?", (nova, nota_id))
                    conn.commit()
                    sucesso = "Nota atualizada com sucesso!"
                else:
                    erro = "A nota deve estar entre 0 e 10."
            except:
                erro = "Nota inválida."
    return render_template("editar_nota.html", aluno=aluno, professor=professor,
                           nota_atual=nota_atual, erro=erro, sucesso=sucesso)

@app.route("/exportar")
def exportar():
    return send_file("export_notas.csv", as_attachment=True)

if __name__ == "__main__":
    app.run(debug=True)
