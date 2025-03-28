
import os
import json
import psycopg2
from flask import Flask, render_template, request, redirect, session, send_file
from datetime import datetime
import csv

app = Flask(__name__)
app.secret_key = "etapa_pg"
CONFIG_FILE = "config_etapa6_2025_1.json"

def carregar_config():
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def get_conn():
    return psycopg2.connect(os.environ["DATABASE_URL"])

def init_db():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute('''
                CREATE TABLE IF NOT EXISTS notas (
                    id SERIAL PRIMARY KEY,
                    aluno TEXT,
                    professor TEXT,
                    nota REAL,
                    datahora TEXT
                )
            ''')
        conn.commit()

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
                with get_conn() as conn:
                    with conn.cursor() as cur:
                        cur.execute("INSERT INTO notas (aluno, professor, nota, datahora) VALUES (%s, %s, %s, %s)",
                                    (aluno, usuario, nota, datetime.now().isoformat()))
                    conn.commit()
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
            query += " AND aluno = %s"
            params.append(aluno)
        if professor:
            query += " AND professor = %s"
            params.append(professor)
        if data_ini:
            query += " AND datahora >= %s"
            params.append(data_ini)
        if data_fim:
            query += " AND datahora <= %s"
            params.append(data_fim + 'T23:59:59')
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                registros = cur.fetchall()
            with open("export_notas.csv", "w", newline="", encoding="utf-8") as f:
                csv.writer(f).writerows([["Aluno", "Professor", "Nota", "DataHora"]] + registros)
    return render_template("relatorio.html", titulo=cfg["titulo"], alunos=cfg["alunos"],
                           professores=list(cfg["usuarios"].keys()), registros=registros,
                           acesso=cfg["usuarios"][usuario]["acesso_relatorio"])

@app.route("/editar-nota/<int:nota_id>", methods=["GET", "POST"])
def editar_nota(nota_id):
    if "usuario" not in session:
        return redirect("/login")
    cfg = carregar_config()
    usuario = session["usuario"]
    if not cfg["usuarios"][usuario]["acesso_relatorio"]:
        return redirect("/")
    erro = sucesso = None
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT aluno, professor, nota FROM notas WHERE id=%s", (nota_id,))
            nota_info = cur.fetchone()
            if not nota_info:
                return "Nota não encontrada."
            aluno, professor, nota_atual = nota_info
            if request.method == "POST":
                try:
                    nova = float(request.form["nova_nota"])
                    if 0 <= nova <= 10:
                        cur.execute("UPDATE notas SET nota=%s WHERE id=%s", (nova, nota_id))
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

@app.route("/resetar")
def resetar():
    # Apenas NASSER pode usar
    if "usuario" not in session or session["usuario"].upper() != "NASSER MAHFOUZ":
        return redirect("/login")
    
    # Limpa todas as notas do banco
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM notas")
        conn.commit()
    
    return """
    <h3>✅ Todas as notas foram apagadas com sucesso!</h3>
    <a href='/'>Voltar ao início</a>
    """

if __name__ == "__main__":
    app.run(debug=True)
