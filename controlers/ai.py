from huggingface_hub import InferenceClient
import json
from pydantic import BaseModel
import requests

def getAnswer(sender_id, question):
    # Recuperar ou inicializar o histórico do usuário
    history = user_history.get(sender_id, [])

    # Adicionar a nova mensagem do usuário ao histórico
    history.append({"role": "user", "content": question})

    # Limitar o histórico a 10 mensagens
    if len(history) > 10:
        history = history[-10:]

    # Criar mensagens para o modelo
    messages = [{"role": "system", "content": data}] + history

    try:
        # Consultar o modelo
        completion = client.chat.completions.create(
            model="Qwen/Qwen2.5-Coder-32B-Instruct",
            messages=messages,
            max_tokens=500
        )
        answer = completion.choices[0].message['content']

        # Processar resposta
        resposta = json.loads(answer)
        if resposta.get("type") == "run_request":
            response = requests.get(resposta["url_to_fetch"])
            resposta_api = response.json()

            if resposta_api:
                ai_response = {
                    "type": "with_api",
                    "ai_message": resposta['if_find_items'],
                    "api_data": resposta_api
                }
            else:
                ai_response = {
                    "type": "without_api",
                    "ai_message": resposta['i_not_found']
                }

            history.append({"role": "assistant", "content": json.dumps(ai_response)})
            user_history[sender_id] = history
            return ai_response
        else:
            user_history[sender_id] = history
            return resposta

    except Exception as e:
        # Adicionar mensagem de erro ao histórico
        error_message = {"type": "error", "message": str(e)}
        history.append({"role": "assistant", "content": json.dumps(error_message)})
        user_history[sender_id] = history
        return error_message

# Configuração do cliente da API da Hugging Face
client = InferenceClient(api_key="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")

with open("controlers/data.txt", "r",encoding="utf-8") as file:
    data = file.read()

user_history = {}

class UserMessage(BaseModel):
    message: str
    sender_id: str
