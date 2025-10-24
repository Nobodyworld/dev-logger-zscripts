"""Domain layer exports for clean architecture interfaces."""

from zscripts.domain.interfaces import (
    AdapterRegistryProtocol,
    ExampleRepositoryProtocol,
    LogAdapterProtocol,
    RedactorProtocol,
    SandboxRunnerFactory,
    SandboxRunnerProtocol,
    SchemaValidatorProtocol,
)
from zscripts.domain.models import SandboxOptions, SandboxResult

__all__ = [
    "AdapterRegistryProtocol",
    "ExampleRepositoryProtocol",
    "LogAdapterProtocol",
    "RedactorProtocol",
    "SandboxRunnerFactory",
    "SandboxRunnerProtocol",
    "SchemaValidatorProtocol",
    "SandboxOptions",
    "SandboxResult",
]
