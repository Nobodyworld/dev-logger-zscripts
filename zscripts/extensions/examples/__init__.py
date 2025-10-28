"""Example extensions for documentation and testing."""

from zscripts.extensions.examples.plugin_echo import EchoExtension, get_extension
from zscripts.extensions.examples.plugin_health import HealthMonitorExtension
from zscripts.extensions.examples.plugin_metrics import MetricsProbeExtension

__all__ = ["EchoExtension", "HealthMonitorExtension", "MetricsProbeExtension", "get_extension"]
