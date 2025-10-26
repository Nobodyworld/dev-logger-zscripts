"""Example extensions for documentation and testing."""

from zscripts.extensions.examples.plugin_echo import EchoExtension, get_extension
from zscripts.extensions.examples.plugin_metrics import MetricsProbeExtension

__all__ = ["EchoExtension", "MetricsProbeExtension", "get_extension"]
