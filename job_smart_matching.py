from openai import OpenAI
import os

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def parse_job(description):
    prompt = f"""
    Extract:
    - Required skills
    - Seniority level
    - Tools/technologies
    - Key responsibilities

    Job Description:
    {description}
    """

    res = client.chat.completions.create(
        model="gpt-5-mini",
        messages=[{"role": "user", "content": prompt}]
    )

    return res.choices[0].message.content
