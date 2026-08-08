import asyncio
from typing import AsyncGenerator
from llama_cpp import Llama


class LargeLanguageModel:
    def __init__(self, model_path: str, n_gpu_layers: int = -1, n_ctx: int = 2048):
        """
        n_gpu_layers=-1 выгружает ВСЕ слои модели на GPU (CUDA).
        """
        self.llm = Llama(
            model_path=model_path,
            n_gpu_layers=n_gpu_layers,
            n_ctx=n_ctx,
            verbose=False
        )
        self.buffer = ""

    def _generate_tokens_sync(self, prompt: str):
        system_prompt = (
            "Ты — задорный и харизматичный радио-DJ Valera. "
            "Твоя задача — прокомментировать прошлую песню и энергично представить следующую. "
            "Отвечай кратко (2-3 предложения max), с юмором и в стиле радиовещания. "
            "Можешь использовать теги звуков [sfx:applause] или [sfx:scratch] для эффектов."
        )
        formatted_prompt = f"<|system|>\n{system_prompt}</s>\n<|user|>\n{prompt}</s>\n<|assistant|>\n"

        return self.llm(
            formatted_prompt,
            max_tokens=150,
            stop=["</s>", "<|user|>"],
            stream=True
        )
    
    @property
    def message(self):
        return self.buffer
    
    async def generate_sentences(self, prompt: str) -> AsyncGenerator[str, None]:
        """Генерирует предложения асинхронно, не блокируя event loop"""
        loop = asyncio.get_running_loop()
        stream = await loop.run_in_executor(None, self._generate_tokens_sync, prompt)

        self.buffer = ""
        for chunk in stream:
            token = chunk["choices"][0]["text"] # type: ignore
            self.buffer += token
            if any(punct in token for punct in [".", "!", "?", "\n"]):
                clean_sentence = self.buffer.strip()
                if clean_sentence:
                    yield clean_sentence
                    self.buffer = ""
            await asyncio.sleep(0)

        if self.buffer.strip():
            yield self.buffer.strip()