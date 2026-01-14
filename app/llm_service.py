import os
from openai import OpenAI
from google import genai
from google.genai import types
from app.utils import log_interaction, logger

import json

# Load prompts from file
from app.database import engine, Prompt, Session, select

def load_prompts():
    """
    Loads prompts from Database. Falls back to defaults if empty.
    """
    with Session(engine) as session:
        statement = select(Prompt)
        results = session.exec(statement).all()
        
        prompts = {
            "system_prompt_claude": "",
            "system_prompt_gemini": ""
        }
        
        for p in results:
            if p.key == "claude":
                prompts["system_prompt_claude"] = p.content
            elif p.key == "gemini":
                prompts["system_prompt_gemini"] = p.content
                
        return prompts

def generate_faqs_text(keyword, brief, web_content):
    """
    Step 1: Generate FAQ text using Claude 3.7 Sonnet via OpenRouter.
    """
    try:
        prompts = load_prompts()
        system_prompt = prompts.get("system_prompt_claude", "")

        api_key = os.environ.get("OPENROUTER_API_KEY")
        site_url = os.environ.get("SITE_URL", "http://localhost:8000")
        site_name = os.environ.get("SITE_NAME", "FAQ Generator")

        if not api_key:
            raise ValueError("OPENROUTER_API_KEY is not set")

        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
        )

        user_content = f"HumanMessage:\nPalabra Clave Principal: {keyword}\nBrief del cliente: {brief}\nTexto completo de la página web: {web_content}"

        log_interaction("Claude Request", user_content, None)

        completion = client.chat.completions.create(
            extra_headers={
                "HTTP-Referer": site_url,
                "X-Title": site_name,
            },
            model="anthropic/claude-3.7-sonnet",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ]
        )
        
        result = completion.choices[0].message.content
        log_interaction("Claude Response", user_content, result)
        return result

    except Exception as e:
        log_interaction("Claude Error", None, None, str(e))
        raise e

def generate_final_html(template_html, faq_texts):
    """
    Step 2: Merge FAQ text into HTML template using Gemini 2.5 Pro.
    """
    try:
        prompts = load_prompts()
        system_prompt = prompts.get("system_prompt_gemini", "")

        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY is not set")

        client = genai.Client(api_key=api_key)

        model = "gemini-2.5-pro" 

        user_message = f"## Plantilla HTML\n{template_html}\n## Textos de preguntas frecuentes\n{faq_texts}"
        
        contents = [
            types.Content(
                role="user",
                parts=[
                    types.Part.from_text(text=user_message),
                ],
            ),
        ]

        generate_content_config = types.GenerateContentConfig(
            temperature=0.3,
            thinking_config=types.ThinkingConfig(
                thinking_budget=-1, 
            ),
            system_instruction=[
                types.Part.from_text(text=system_prompt),
            ],
        )

        log_interaction("Gemini Request", user_message, None)
        
        # User code used streaming. I'll collect it.
        response_text = ""
        # Note: The user provided code uses generate_content_stream
        # I often prefer non-streaming for simple API response handling, but will follow pattern if forced.
        # User code: "for chunk in client.models.generate_content_stream..."
        
        # Simplified for non-streaming to ensure I get full text easily
        response = client.models.generate_content(
           model=model,
           contents=contents,
           config=generate_content_config
        )
        response_text = response.text

        log_interaction("Gemini Response", user_message, response_text)
        return response_text

    except Exception as e:
        log_interaction("Gemini Error", None, None, str(e))
        raise e
