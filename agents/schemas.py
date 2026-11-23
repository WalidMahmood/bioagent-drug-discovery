"""Pydantic schemas for all agent I/O (Master #38).
Standardized structured contracts with validation, safety guardrails, and audit tracking.
"""
from typing import List, Literal, Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator

ClaimType = Literal["observed", "supported", "hypothesis"]


def _coerce_str_list(v: Any) -> List[str]:
    """Coerce a single string or None from small local LLMs into a clean List[str]."""
    if v is None:
        return []
    if isinstance(v, str):
        cleaned = v.strip()
        return [cleaned] if cleaned else []
    if isinstance(v, list):
        return [str(item).strip() for item in v if item is not None and str(item).strip()]
    return [str(v).strip()]


class Comparison(BaseModel):
    group_a: str = Field(description="Intervention or perturbation group")
    group_b: str = Field(description="Reference or control group")


class Plan(BaseModel):
    analysis_goal: str
    dataset: str
    organism: str = "Homo sapiens"
    data_type: str = "counts"  # counts, fpkm, cuffdiff
    comparison: Comparison
    design: str
    de_method: str
    required_steps: List[str] = Field(
        default_factory=lambda: [
            "validate_metadata",
            "run_differential_expression",
            "run_enrichment",
            "retrieve_evidence",
            "verify_results",
        ]
    )
    safety_guardrails: List[str] = Field(
        default_factory=lambda: [
            "refuse_fpkm_deseq2",
            "require_bh_fdr",
            "require_hedged_hypothesis",
            "non_clinical_disclaimer",
        ]
    )

    @field_validator("required_steps", "safety_guardrails", mode="before")
    @classmethod
    def _coerce_plan_lists(cls, v: Any) -> List[str]:
        return _coerce_str_list(v)


class TopGene(BaseModel):
    gene: str
    log2FC: float
    padj: Optional[float] = None
    pvalue: Optional[float] = None
    direction: Literal["up", "down"]


class SigPathway(BaseModel):
    source: str  # GO, Reactome, KEGG
    term: str
    adjP: float
    overlap: str


class ComputationalResult(BaseModel):
    dataset: str
    data_type: str = "counts"
    inferential: bool = True  # False for descriptive FPKM/TPM without inferential p-values
    contrast: str
    n_total_tested: int = 0
    n_sig: int
    n_up: int
    n_down: int
    padj_threshold: float = 0.05
    top_genes: List[TopGene]
    sig_pathways: List[SigPathway]
    execution_log: List[str] = Field(default_factory=list)


class InterpretationClaim(BaseModel):
    statement: str
    type: ClaimType  # observed (direct numbers), supported (literature/pathway corroborated), hypothesis (mechanistic speculation)
    genes: List[str] = Field(default_factory=list)
    pathways: List[str] = Field(default_factory=list)
    hedged: bool = Field(default=True, description="True if statement uses appropriate scientific uncertainty language")

    @field_validator("genes", "pathways", mode="before")
    @classmethod
    def _coerce_claim_lists(cls, v: Any) -> List[str]:
        return _coerce_str_list(v)


class Interpretation(BaseModel):
    observations: List[str] = Field(default_factory=list)
    claims: List[InterpretationClaim] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)
    uncertainty: List[str] = Field(default_factory=list)
    pruned_claims: List[str] = Field(default_factory=list)
    disclaimer: str = (
        "RESEARCH PROTOTYPE ONLY: This automated interpretation is generated for computational biology "
        "research and term-project evaluation. It is not approved for clinical diagnostics or medical decisions."
    )

    @field_validator("observations", "limitations", "uncertainty", "pruned_claims", mode="before")
    @classmethod
    def _coerce_interp_lists(cls, v: Any) -> List[str]:
        return _coerce_str_list(v)


class EvidenceRecord(BaseModel):
    claim: str
    query: str
    source_id: str
    source_db: str  # DE_computation, GO, Reactome, KEGG, Pathway_Enrichment
    snippet: str
    relevance: float
    timestamp: str


class DrugCandidate(BaseModel):
    drug_id: str = ""
    drug_name: str
    drug_type: str = "Small molecule"
    target_gene: str
    target_log2FC: float
    recommended_flip: str
    action_type: str = "Unspecified"
    mechanism: str = ""
    clinical_stage: str = "UNKNOWN"
    clinical_stage_label: str = "Investigated"
    stage_rank: int = 0
    indications: List[str] = Field(default_factory=list)
    moa_audit_status: Literal["CONCORDANT", "DISCORDANT_BLOCKED", "NEUTRAL_REVIEW"] = "NEUTRAL_REVIEW"
    moa_audit_note: str = ""
    url: str = ""


class TargetDossierItem(BaseModel):
    gene: str
    ensembl_id: Optional[str] = None
    approved_name: str = ""
    log2FC: float
    padj: Optional[float] = None
    direction: Literal["up", "down"]
    recommended_flip: str
    expected_moa_class: Literal["inhibitory", "activating"]
    flip_rationale: str = ""
    priority_score: float = 0.0
    evidence_tier: str = "Tier 3: Novel Genetic Flip Target"
    score_breakdown: Dict[str, float] = Field(default_factory=dict)
    is_essential: Optional[bool] = None
    tractable_modalities: List[str] = Field(default_factory=list)
    safety_liabilities_count: int = 0
    safety_events_sample: List[str] = Field(default_factory=list)
    safety_warning: Optional[str] = None
    total_known_drugs: int = 0
    concordant_drugs_count: int = 0
    associated_diseases: List[Dict[str, Any]] = Field(default_factory=list)
    opentargets_url: str = ""


class CriticVerdict(BaseModel):
    status: Literal["PASS", "FAIL"]
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    corrections: List[str] = Field(default_factory=list)
    statistical_checks_passed: bool = True
    biological_grounding_passed: bool = True
    safety_guardrails_passed: bool = True
    therapeutic_moa_checks_passed: bool = True
    audit_scores: Dict[str, Any] = Field(default_factory=dict)
