"""Shared network domain models and IP operations."""

from .device.models import NetworkDevice
from .bgp.models import AsPrefix, AutonomousSystem, AsGroupingResult
from .bgp.grouping import group_as_prefixes
from .bgp.exceptions import DuplicatePrefixError


__all__ = ["NetworkDevice", "AsPrefix", "AutonomousSystem", "AsGroupingResult", "group_as_prefixes", "DuplicatePrefixError"]
