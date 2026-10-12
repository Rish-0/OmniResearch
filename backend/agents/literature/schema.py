"""
Data schemas for Literature Agent in OmniResearch.
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class PaperMetadata(BaseModel):
    """
    Structured metadata for a scholarly paper.
    """
    paper_id: str = Field(..., description="Unique paper identifier (DOI, arXiv ID, or URL)")
    title: str = Field(..., description="Paper title")
    authors: List[str] = Field(default_factory=list, description="List of authors")
    abstract: str = Field(default="", description="Paper abstract or summary")
    year: Optional[int] = Field(default=None, description="Publication year")
    url: Optional[str] = Field(default=None, description="Direct URL or DOI link to paper")
    source: str = Field(default="openalex", description="Source repository (openalex, arxiv, semantic_scholar, baseline)")
    citation_count: int = Field(default=0, description="Number of citations")


class LiteratureReviewResult(BaseModel):
    """
    Structured outcome of a literature review task.
    """
    query: str = Field(..., description="Search query executed")
    papers: List[PaperMetadata] = Field(default_factory=list, description="Retrieved paper metadata list")
    summary: str = Field(..., description="Synthesized literature review summary")
    total_found: int = Field(default=0, description="Total number of papers retrieved")
