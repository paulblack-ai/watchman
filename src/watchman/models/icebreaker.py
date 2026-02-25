"""IcebreakerAI tool registry schema as Pydantic models.

Placeholder schema -- update when real IcebreakerAI registry schema is obtained (INFRA-02).
These models define the expected structure of tool entries for the IcebreakerAI platform.
"""

from datetime import datetime

from pydantic import BaseModel


class IcebreakerToolEntry(BaseModel):
    """A tool entry compatible with the IcebreakerAI tool registry.

    This is a placeholder schema based on expected fields. Must be updated
    when the actual IcebreakerAI registry schema is obtained.
    """

    name: str
    description: str
    capabilities: list[str]
    pricing: str | None = None
    api_surface: str | None = None
    integration_hooks: list[str] = []
    source_url: str | None = None
    discovered_at: datetime | None = None
