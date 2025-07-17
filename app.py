from flask import Flask, request, jsonify, render_template, send_file
import requests
import pandas as pd
import io
import re
import time
import sqlite3
from datetime import datetime
import os

app = Flask(__name__)

TOKEN_URL = "https://fgtsoff.facta.com.br/gera-token"
TOKEN_AUTH_HEADER = "Basic OTY1NTI6ZjRzaXV0azJ1ZWNhNDVldXhnOXc="
API_URL = "https://fgtsoff.facta.com.br/fgts/base-offline"

ultimos_resultados = []

def gerar_token():
    response = requests.get(
        TOKEN_URL,
        headers={
            "Authorization": TOKEN_AUTH_HEADER,
            "Accept": "application/json",
            "User-Agent": "insomnia/11.2.0"
        }
    )
    data = response.json()
    return data.get("token")

def init_db():
    conn = sqlite3.connect("consultas.db")
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS consultas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cpf TEXT,
            resultado TEXT,
            data TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/consultar", methods=["POST"])
def consultar():
    cpfs = request.json.get("cpfs", [])
    max_tentativas = int(request.json.get("tentativas", 1))

    resultados = []
    token = gerar_token()
    if not token:
        return jsonify({"erro": "Não foi possível gerar o token"}), 500

    for cpf in cpfs:
        tentativa = 0
        resultado_final = {
            "CPF": cpf,
            "Resultado": "Erro",
        }

        while tentativa < max_tentativas:
            tentativa += 1
            try:
                response = requests.get(
                    API_URL,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Accept": "application/json",
                        "User-Agent": "insomnia/11.2.0"
                    },
                    params={"cpf": cpf}
                )

                data = response.json()
                mensagem = data.get("mensagem", "")
                erro_flag = data.get("erro", True)

                if "base offline indisponível" in mensagem.lower():
                    if tentativa < max_tentativas:
                        time.sleep(1)
                        continue
                    else:
                        resultado_final["Resultado"] = "Consulta indisponível"
                        break

                if not erro_flag:
                    match = re.search(r"\d{2}/\d{2}/\d{4}", mensagem)
                    data_limite = match.group(0) if match else "Data não informada"
                    resultado_final["Resultado"] = f"Autorizado até {data_limite}"
                    break

                if erro_flag:
                    resultado_final["Resultado"] = "Não autorizado"
                    break

            except Exception as e:
                resultado_final["Resultado"] = f"Erro: {str(e)}"
                break

        resultados.append(resultado_final)

        conn = sqlite3.connect("consultas.db")
        c = conn.cursor()
        c.execute("INSERT INTO consultas (cpf, resultado, data) VALUES (?, ?, ?)", (
            resultado_final["CPF"],
            resultado_final["Resultado"],
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ))
        conn.commit()
        conn.close()

    return jsonify(resultados)

@app.route("/recuperar-consultas", methods=["GET"])
def recuperar_consultas():
    conn = sqlite3.connect("consultas.db")
    c = conn.cursor()
    c.execute("SELECT cpf, resultado, data FROM consultas ORDER BY id DESC LIMIT 100")
    dados = [{"CPF": row[0], "Resultado": row[1], "Data": row[2]} for row in c.fetchall()]
    conn.close()
    return jsonify(dados)

os.makedirs("recuperacoes", exist_ok=True)

@app.route("/baixar-recuperadas", methods=["GET"])
def baixar_recuperadas():
    conn = sqlite3.connect("consultas.db")
    c = conn.cursor()
    c.execute("SELECT cpf, resultado, data FROM consultas ORDER BY id DESC LIMIT 100")
    rows = c.fetchall()
    conn.close()

    df = pd.DataFrame(rows, columns=["CPF", "Resultado", "Data"])
    from datetime import datetime

    data_agora = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    nome_arquivo = f"ultimas_consultas_{data_agora}.xlsx"
    caminho = os.path.join("recuperacoes", nome_arquivo)

    df.to_excel(caminho, index=False)
    return send_file(caminho, as_attachment=True)

@app.route("/baixar-excel", methods=["POST"])
def baixar_excel():
    dados = request.json.get("resultados", [])
    df = pd.DataFrame(dados)
    output = io.BytesIO()
    with pd.ExcelWriter(output) as writer:
        df.to_excel(writer, index=False, sheet_name="Resultados")
    output.seek(0)
    return send_file(
        output,
        as_attachment=True,
        download_name="resultado_consulta.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

if __name__ == "__main__":
    app.run(debug=True)
