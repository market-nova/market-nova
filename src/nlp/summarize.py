
# Optional: plug in OpenAI or Anthropic for summaries. Defaults to a no-op.
import os

def summarize(text: str, provider: str = "", api_key: str = "", model: str = "", max_tokens: int = 600, temperature: float = 0.2) -> str:
    text = text[:8000]  # keep it short by default
    if provider == "openai":
        try:
            from openai import OpenAI
            client = OpenAI(api_key=api_key)
            resp = client.chat.completions.create(
                model=model or "gpt-4o-mini",
                messages=[{"role":"system","content":"You write concise finance summaries."},
                          {"role":"user","content":f"Summarize key risks and changes:\n\n{text}"}],
                max_tokens=max_tokens, temperature=temperature)
            return resp.choices[0].message.content
        except Exception as e:
            return f"[OpenAI summary failed: {e}]"
    elif provider == "anthropic":
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
            msg = client.messages.create(
                model=model or "claude-3-haiku-20240307",
                max_tokens=max_tokens,
                temperature=temperature,
                system="You write concise finance summaries.",
                messages=[{"role":"user","content":f"Summarize key risks and changes:\n\n{text}"}])
            return msg.content[0].text
        except Exception as e:
            return f"[Anthropic summary failed: {e}]"
    return "[LLM disabled - no summary]"
