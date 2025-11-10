# src/llm_client.py
import os
import requests
from dotenv import load_dotenv

# Load variables from our .env file
load_dotenv()

# Get the API key from the environment
API_KEY = os.environ.get("GROQ_API_KEY")

# Groq's API URL (OpenAI-compatible endpoint)
API_URL = "https://api.groq.com/openai/v1/chat/completions"

def get_llm_response(prompt: str) -> str:
    """
    Sends a prompt to the Groq API and returns the response.
    """
    if not API_KEY:
        # Changed the key name in the error message
        return "Error: GROQ_API_KEY not found. Please check your .env file."

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }

    data = {
        "model": "llama-3.3-70b-versatile",  # To change the model, just update this line
        "messages": [
            {"role": "system", "content": "You are a helpful software engineering assistant."},
            {"role": "user", "content": prompt}
        ]
    }

    try:
        response = requests.post(API_URL, headers=headers, json=data)

        # The JSON path for OpenAI-compatible APIs
        if response.status_code == 200:
            result = response.json()
            return result['choices'][0]['message']['content']
        else:
            return f"Error: API request failed with status {response.status_code}. Response: {response.text}"

    except Exception as e:
        return f"An error occurred: {e}"

# This part lets us test the file directly
if __name__ == "__main__":
    print("Testing LLM Client with Groq...")
    test_prompt = "Hello, Groq! In one sentence, what is a postcondition?"
    response = get_llm_response(test_prompt)
    print(f"Prompt: {test_prompt}")
    print(f"Response: {response}")