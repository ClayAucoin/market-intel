import time

import ollama


MODEL = "qwen2.5:3b"


def analyze_text(
    prompt,
    format_schema=None,
    num_predict=1200,
):
    start = time.time()

    response = ollama.chat(
        model=MODEL,
        messages=[
            {
                "role": "user",
                "content": prompt,
            }
        ],
        format=format_schema or "json",
        options={
            "num_predict": num_predict,
            "temperature": 0,
        },
    )

    elapsed = time.time() - start

    print(
        f"AI response time: {elapsed:.2f} seconds"
    )

    return response["message"]["content"]