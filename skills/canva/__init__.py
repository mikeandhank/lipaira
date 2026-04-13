"""
Canva integration package for Lipaira.

Provides skills for interacting with Canva designs:
- CanvaGetDesignsSkill: Fetch designs from Canva
- CanvaCreateDesignSkill: Create new designs in Canva

Key functions/classes:
    CanvaGetDesignsSkill: Retrieves user's designs
    CanvaCreateDesignSkill: Creates new designs with templates
"""

from skills.canva.designs import CanvaGetDesignsSkill, CanvaCreateDesignSkill
__all__ = ["CanvaGetDesignsSkill", "CanvaCreateDesignSkill"]
