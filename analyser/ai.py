from model_provider import generate_response

if __name__ == "__main__":
    system_prompt = "You are a helpful assistant."
    user_message = 'text'

    response = generate_response(system_prompt, user_message)
    print("AI Response:", response)