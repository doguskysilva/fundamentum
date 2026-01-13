from typing import Protocol

class SettingsProtocol(Protocol):
    SERVICE_NAME: str
    ENV: str
    DEBUG: bool
    VERSION: str
