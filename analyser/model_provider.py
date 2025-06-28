import requests
import os
from dotenv import load_dotenv
load_dotenv()

api_key = os.environ.get("API_KEY_OPENROUTER")


def generate_response(system_prompt, user_message, model="openai/gpt-4"):
    print("Sending request to OpenRouter")
    url = "https://openrouter.ai/api/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ],
        "temperature": 0.0
    }

    # print("=== PAYLOAD ===")
    # print(json.dumps(payload, indent=2))

    response = requests.post(url, headers=headers, json=payload)
    response.raise_for_status()

    return response.json()["choices"][0]["message"]["content"]