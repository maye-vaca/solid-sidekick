"""Small mesh-CAD foundation: millimetre geometry, placed parts and offline exports."""

from .assembly import Assembly, Instance, Part, Placement
from .regions import VisualRegion

__all__ = ["Assembly", "Instance", "Part", "Placement", "VisualRegion"]
