import httpx
import os
from dotenv import load_dotenv
load_dotenv()

api_key = os.environ.get("API_KEY_OPENROUTER")


async def generate_response(prompt, model="anthropic/claude-sonnet-4"):
    print("Sending request to OpenRouter")
    url = "https://openrouter.ai/api/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": model,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.0
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json=payload, timeout=60.0)
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]

    print(f"[DEBUG] AI Response: {content}")

    return content
