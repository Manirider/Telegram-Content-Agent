"""JSON parsing and recovery utilities."""
import json
import re

from app.llm.schemas import ContentGenerationResult
from app.utils.exceptions import LLMValidationError
from app.utils.logging import get_logger

logger = get_logger(__name__)


def parse_llm_json(content: str) -> ContentGenerationResult:
    """Parse LLM response JSON with recovery attempts."""
    # Attempt 1: Direct parse
    try:
        data = json.loads(content)
        return ContentGenerationResult(**data)
    except json.JSONDecodeError:
        pass
    except (ValueError, TypeError) as e:
        logger.debug("Direct parse validation failed", error=str(e))
    
    # Attempt 2: Extract from markdown fences
    try:
        data = _extract_json_from_fences(content)
        return ContentGenerationResult(**data)
    except (ValueError, TypeError, LLMValidationError) as e:
        logger.debug("Fence extraction failed", error=str(e))
    
    # Attempt 3: Extract JSON object from text
    try:
        data = _extract_json_object(content)
        return ContentGenerationResult(**data)
    except (ValueError, TypeError, LLMValidationError) as e:
        logger.debug("Object extraction failed", error=str(e))
    
    raise LLMValidationError("Failed to parse valid JSON from LLM response")


def _extract_json_from_fences(content: str) -> dict:
    """Extract JSON from markdown code fences."""
    # Try ```json ... ``` or ``` ... ```
    fence_pattern = r'```(?:json)?\s*(\{.*?\})\s*```'
    matches = re.findall(fence_pattern, content, re.DOTALL)
    
    for match in matches:
        try:
            return json.loads(match)
        except json.JSONDecodeError:
            continue
    
    raise LLMValidationError("No valid JSON in code fences")


def _extract_json_object(content: str) -> dict:
    """Extract JSON object from mixed content."""
    # Find the first complete JSON object
    # This is a simplified approach - looks for balanced braces
    start = content.find('{')
    if start == -1:
        raise LLMValidationError("No JSON object found")
    
    # Find matching closing brace
    brace_count = 0
    for i, char in enumerate(content[start:], start):
        if char == '{':
            brace_count += 1
        elif char == '}':
            brace_count -= 1
            if brace_count == 0:
                candidate = content[start:i+1]
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError:
                    continue
    
    raise LLMValidationError("No valid JSON object found")


def validate_generation_result(result: ContentGenerationResult) -> list[str]:
    """Validate generation result beyond Pydantic validation."""
    errors = []
    
    # X post length (Pydantic validates but double-check)
    if len(result.variants.x_post) > 280:
        errors.append(f"X post exceeds 280 characters: {len(result.variants.x_post)}")
    
    # Non-empty checks (Pydantic validates but double-check)
    if not result.title.strip():
        errors.append("Title is empty")
    if not result.rationale.strip():
        errors.append("Rationale is empty")
    if not result.category.strip():
        errors.append("Category is empty")
    if not result.variants.x_post.strip():
        errors.append("X post is empty")
    if not result.variants.linkedin_post.strip():
        errors.append("LinkedIn post is empty")
    
    # Distinct variants
    if result.variants.x_post.strip() == result.variants.linkedin_post.strip():
        errors.append("X post and LinkedIn post are identical")
    
    # Content type validation will be done at service layer
    
    return errors


def repair_x_post(x_post: str, linkedin_post: str, max_length: int = 280) -> str:
    """Attempt to repair X post that's too long."""
    if len(x_post) <= max_length:
        return x_post
    
    # Try to truncate at word boundary
    truncated = x_post[:max_length]
    last_space = truncated.rfind(' ')
    
    if last_space > max_length * 0.7:
        return truncated[:last_space].rstrip() + "..."
    
    # Hard truncate with ellipsis
    return x_post[:max_length - 3] + "..."