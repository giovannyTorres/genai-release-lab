from typing import Literal
from datetime import date
from pydantic import BaseModel, ConfigDict, Field, model_validator


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ToolCall(Strict):
    name: str = Field(min_length=1, max_length=100)
    arguments: dict


class Authorization(Strict):
    actor_role: str
    allowed_roles: list[str]
    action: str
    authorized: bool
    # A model-produced assertion is not trusted backend evidence.
    evidence_source: Literal["backend_trace", "model_claim"] = "model_claim"


class Output(Strict):
    answer: str = Field(max_length=20000)
    citations: list[str] = Field(default_factory=list, max_length=100)
    tool_calls: list[ToolCall] = Field(default_factory=list, max_length=20)
    authorization: Authorization | None = None
    tokens: int | None = Field(default=None, ge=0)


class RagExpectation(Strict):
    allowed_citations: list[str]
    required_citations: list[str]
    answer_contains: list[str] = Field(default_factory=list)
    abstain: bool = False
    answer: str = ""


class AgentExpectation(Strict):
    tool_calls: list[ToolCall]
    authorization_required: bool
    allowed_roles: list[str]
    action: str


class Case(Strict):
    id: str = Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9_-]+$")
    split: Literal["development", "final"]
    kind: Literal["rag", "agent"]
    prompt: str = Field(min_length=1, max_length=20000)
    context: str = Field(max_length=30000)
    expected: dict

    @model_validator(mode="after")
    def validate_expectation(self):
        schema = RagExpectation if self.kind == "rag" else AgentExpectation
        schema.model_validate(self.expected)
        return self


class OutputRecord(Strict):
    case_id: str
    output: dict


class DatasetImport(Strict):
    name: str = Field(min_length=1, max_length=100)
    version: str = Field(min_length=1, max_length=40)
    format: Literal["json", "jsonl"]
    content: str = Field(max_length=2_000_000)


class ConfigurationInput(Strict):
    name: str = Field(min_length=1, max_length=100)
    version: str = Field(min_length=1, max_length=40)
    threshold: float = Field(default=1.0, ge=0, le=1)
    require_llm: bool = False
    rubric: str = Field(
        default="Check whether the answer is supported by the provided context. Pass only grounded answers.",
        max_length=5000,
    )
    rubric_version: str = "grounding-v1"
    provider: Literal["openai", "gemini"] = "openai"
    model: str = Field(default="gpt-4.1-mini", max_length=100)
    price_per_million_tokens: float | None = Field(default=None, ge=0)
    price_date: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")

    @model_validator(mode="after")
    def pricing(self):
        if self.price_date is not None:
            date.fromisoformat(self.price_date)
        if (self.price_date is None) != (self.price_per_million_tokens is None):
            raise ValueError("A price and its date must be configured together")
        return self


class JobInput(Strict):
    dataset_id: str
    configuration_id: str
    label: str = Field(min_length=1, max_length=100)
    source: Literal["fixture", "api", "endpoint"] = "fixture"
    fixture: Literal["reference", "regression"] = "reference"
    endpoint_id: str | None = None


class ResultsImport(Strict):
    dataset_id: str
    configuration_id: str
    label: str = Field(min_length=1, max_length=100)
    format: Literal["json", "jsonl"]
    content: str = Field(max_length=2_000_000)


class HumanReview(Strict):
    case_id: str
    verdict: Literal["pass", "fail"]
    comment: str = Field(min_length=5, max_length=2000)


class Approval(Strict):
    comment: str = Field(min_length=5, max_length=2000)


class EndpointInput(Strict):
    name: str = Field(min_length=1, max_length=100)
    url: str = Field(max_length=2000)


class JudgeResult(Strict):
    verdict: Literal["pass", "fail"]
    reason: str = Field(max_length=2000)
