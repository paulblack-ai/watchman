"""IcebreakerAI tool registry schema as Pydantic models.

Placeholder schema -- update when real IcebreakerAI registry schema is obtained (INFRA-02).
These models define the expected structure of tool entries for the IcebreakerAI platform.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class IcebreakerToolEntry(BaseModel):
    """A tool entry compatible with the IcebreakerAI tool registry.

    This is a placeholder schema based on expected fields. Must be updated
    when the actual IcebreakerAI registry schema is obtained.
    """

    name: str
    description: str
    capabilities: List[str]
    pricing: Optional[str] = None
    api_surface: Optional[str] = None
    integration_hooks: List[str] = []
    source_url: Optional[str] = None
    discovered_at: Optional[datetime] = None
