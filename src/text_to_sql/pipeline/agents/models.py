"""Pydantic models for structured LLM output in analytical agents."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class QueryClassification(BaseModel):
    """LLM classification of a user query as simple or analytical."""

    query_type: Literal["simple", "analytical"] = Field(
        description="Whether this is a simple lookup/count query or a complex analytical query"
    )
    reasoning: str = Field(
        description="Brief explanation of why this classification was chosen"
    )


class AnalysisStep(BaseModel):
    """A single step in a multi-step analysis plan."""

    description: str = Field(description="What this step aims to discover")
    sql_hint: str = Field(description="Guidance for the SQL query to generate")
    purpose: str = Field(description="How this step contributes to the overall analysis")


class AnalysisPlan(BaseModel):
    """A structured plan for multi-step analytical queries."""

    steps: list[AnalysisStep] = Field(
        description="Ordered list of analysis steps (max 7)",
        max_length=7,
    )
    synthesis_guidance: str = Field(
        description="Instructions for how to synthesize results across all steps"
    )
