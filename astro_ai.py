import asyncio
import logging
from typing import Optional
from gigachat import GigaChat
from gigachat.models import Messages

logger = logging.getLogger(__name__)

class AstroAI:
    def __init__(self, auth_key: str):
        self.client = GigaChat(credentials=auth_key, verify_ssl_certs=True, timeout=15)
        self._semaphore = asyncio.Semaphore(6)

    async def generate(self, prompt: str, max_tokens: int = 400) -> Optional[str]:
        async with self._semaphore:
            for attempt in range(2):
                try:
                    response = await asyncio.to_thread(
                        self.client.chat,
                        messages=[Messages(role="user", content=prompt)],
                        temperature=0.8,
                        max_tokens=max_tokens
                    )
                    text = response.choices[0].message.content.strip()
                    return text if len(text) > 20 else None
                except Exception as e:
                    logger.warning(f"GigaChat попытка {attempt+1} не удалась: {e}")
                    if attempt == 1: return None
                    await asyncio.sleep(2)
        return None