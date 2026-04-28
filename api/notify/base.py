"""NotificationChannel ABC。"""
from abc import ABC, abstractmethod

from api.schemas.notify import ChannelResult, NotificationPayload


class NotificationChannel(ABC):
    """通知通道抽象。實作類別必須提供 name 屬性。"""

    name: str = ""

    @abstractmethod
    def send(
        self,
        payload: NotificationPayload,
        recipients: list[str],
    ) -> list[ChannelResult]:
        """發送通知。回傳每個 recipient 的結果。"""

    @abstractmethod
    def health_check(self) -> bool:
        """驗證 credential / endpoint 可達。不送訊息。"""

    @abstractmethod
    def is_configured(self) -> bool:
        """是否已配置必要環境變數。"""
