from pydantic import BaseModel, Field, EmailStr
from typing import List, Dict, Any, Optional, Union
from mcp.types import TextContent
from enum import Enum

class UserPreferences(BaseModel):
    language: str = Field(..., description="Preferred language for communication")
    priority: str = Field(..., description="Task priority level")
    email_format: str = Field(..., description="Preferred email format")
    verification_level: str = Field(..., description="Level of verification required")

class VerificationType(str, Enum):
    EMAIL_VALIDATION = "email_validation"
    CALCULATION = "calculation"
    ASCII_VALUES = "ascii_values"
    CONTENT_VALIDATION = "content_validation"
    GENERAL = "general"

class VerificationChecks(BaseModel):
    type: VerificationType
    checks: List[str]

class ReasoningStep(BaseModel):
    description: str
    type: str
    confidence: float

class ShowReasoningInput(BaseModel):
    steps: List[Union[str, ReasoningStep]] = Field(..., description="List of reasoning steps or step descriptions")

class GetAsciiInput(BaseModel):
    string: str = Field(..., description="String to get ASCII values for")

class CalculateExponentialInput(BaseModel):
    numbers: List[int] = Field(..., description="List of numbers to calculate exponential sum for")

class SendEmailInput(BaseModel):
    to: EmailStr = Field(..., description="Recipient email address")
    subject: str = Field(..., description="Email subject")
    body: str = Field(..., description="Email body content")
    image_path: Optional[str] = None

class FunctionCall(BaseModel):
    function: str
    parameters: Dict[str, Any]
    verification: VerificationChecks
    reasoning: ReasoningStep

class FinalAnswer(BaseModel):
    status: str
    message: str
    summary: List[str]
    confidence: float
    fallback_suggestions: Optional[List[str]] = None

class EmailResponse(BaseModel):
    content: TextContent 