"""LLM output schemas using Pydantic."""
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class Variants(BaseModel):
    """Platform-specific content variants."""
    x_post: str = Field(..., description="X/Twitter post (<= 280 chars)")
    linkedin_post: str = Field(..., description="LinkedIn post (longer, professional)")
    
    @field_validator("x_post")
    @classmethod
    def validate_x_length(cls, v: str) -> str:
        if len(v) > 280:
            raise ValueError(f"X post exceeds 280 characters: {len(v)}")
        if not v.strip():
            raise ValueError("X post cannot be empty")
        return v
    
    @field_validator("linkedin_post")
    @classmethod
    def validate_linkedin_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("LinkedIn post cannot be empty")
        return v


class ContentGenerationResult(BaseModel):
    """Structured result from LLM generation."""
    title: str = Field(..., description="Compelling title for the content")
    rationale: str = Field(..., description="Editorial rationale for the content")
    category: str = Field(..., description="Single relevant category")
    variants: Variants = Field(..., description="Platform-specific variants")
    
    @field_validator("title", "rationale", "category")
    @classmethod
    def validate_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Field cannot be empty")
        return v
    
    @field_validator("category")
    @classmethod
    def validate_category(cls, v: str) -> str:
        # Could add predefined categories here if needed
        return v.strip()


class LLMRequest(BaseModel):
    """Request to LLM provider."""
    system_prompt: str
    user_prompt: str
    temperature: float = 0.7
    max_tokens: int = 4000
    response_format: Literal["json"] = "json"