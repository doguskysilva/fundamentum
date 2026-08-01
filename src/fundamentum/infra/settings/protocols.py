from typing import Any, Protocol


class SettingsProtocol(Protocol):
    service_name: str
    service_version: str
    environment: str
    log_level: str
    enable_json_logging: bool


class ServiceSettingsProtocol(Protocol):
    """Accepts any settings object with arbitrary attributes.

    Deliberately unconstrained: `ServiceRegistry` resolves peer service URLs
    by probing for attributes named `{service}_base_url`, and those names are
    defined per-subclass by each microservice, not known ahead of time. A
    protocol declaring fixed fields (like `SettingsProtocol` above) couldn't
    express that, so this one only asserts "any attribute is readable".
    """

    def __getattribute__(self, name: str) -> Any: ...
