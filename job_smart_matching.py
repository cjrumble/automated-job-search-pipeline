import os
import json
from openai import OpenAI

# Lazy-initialize the client so missing API key doesn't crash on import
_client = None


def _get_client():
    global _client
    if _client is None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise EnvironmentError(
                "OPENAI_API_KEY is not set. Add it to your .env file."
            )
        _client = OpenAI(api_key=api_key)
    return _client


def parse_job(description):
    """
    Uses OpenAI to extract structured data from a job description.
    Returns a dict with keys: skills, seniority, tools, responsibilities.
    Returns {} on any failure so the pipeline can continue.
    """
    if not description or not description.strip():
        return {}

    prompt = f"""Analyze the following job description and return ONLY a JSON object
with these exact keys (no extra text, no markdown):
{{
  "skills": ["list", "of", "required", "technical", "skills"],
  "seniority": "one of: junior | mid | senior | staff | unknown",
  "tools": ["list", "of", "tools", "and", "technologies"],
  "responsibilities": ["top", "3", "responsibilities"]
}}

Job Description:
{description[:3000]}
"""

    try:
        client = _get_client()
        res = client.chat.completions.create(
            model="gpt-4o-mini",          # FIX 5: corrected — previous model name did not exist
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            max_tokens=500,
            temperature=0.2
        )
        return json.loads(res.choices[0].message.content)
    except EnvironmentError as e:
        print(f"[parse_job] Config error: {e}")
        return {}
    except json.JSONDecodeError:
        print("[parse_job] Could not parse OpenAI response as JSON.")
        return {}
    except Exception as e:
        print(f"[parse_job] OpenAI call failed: {e}")
        return {}
