from typing import Any, Protocol


class SettingsProtocol(Protocol):
    service_name: str
    service_version: str
    environment: str
    log_level: str
    enable_json_logging: bool


class ServiceSettingsProtocol(Protocol):
    
    def __getattribute__(self, name: str) -> Any: ...
