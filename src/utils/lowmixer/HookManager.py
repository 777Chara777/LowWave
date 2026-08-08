import asyncio
from typing import Callable, Dict, List

class HookManager:
    """Полноценная шина событий с разделением по тегам (event_name)"""
    def __init__(self):
        self._listeners: Dict[str, List[Callable]] = {}

    def subscribe(self, event_name: str, callback: Callable):
        """Подписка на конкретное событие"""
        if event_name not in self._listeners:
            self._listeners[event_name] = []
        self._listeners[event_name].append(callback)

    async def trigger(self, event_name: str, *args, **kwargs):
        """Вызов подписчиков только для переданного event_name"""
        if event_name not in self._listeners:
            return

        for callback in self._listeners[event_name]:
            if asyncio.iscoroutinefunction(callback):
                await callback(*args, **kwargs)
            else:
                callback(*args, **kwargs)