from flask import Flask, request, jsonify, render_template, send_file
import requests
import pandas as pd
import io
import re
import time

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

    return jsonify(resultados)

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

app = app
