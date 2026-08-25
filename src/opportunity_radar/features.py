from __future__ import annotations

import re

from opportunity_radar.phase3_config import Taxonomy
from opportunity_radar.phase3_models import DeterministicFeature, SemanticJobInput


RULE_VERSION = "concept-dictionary-v1"

# Neutral evidence patterns. They describe job content and contain no candidate identity.
CONCEPT_PATTERNS: dict[str, tuple[str, ...]] = {
    "ai_enabled_work": (r"\bartificial intelligence\b", r"\bAI\b", r"machine learning", r"generative AI"),
    "business_analytics": (r"business analytics", r"data analysis", r"analytical insights", r"generate.+insights", r"quantitative.+methods"),
    "analytical_problem_solving": (r"problem.solving", r"formulating hypotheses", r"analytical", r"solve.+challenges"),
    "decision_support": (r"decision.ready", r"decision support", r"recommendations", r"support.+decisions"),
    "stakeholder_management": (r"stakeholders?", r"international clients", r"executive", r"získáte jejich důvěru", r"komunikační"),
    "transformation": (r"transformation", r"transform", r"change initiatives", r"digitalizac", r"řízení změnových"),
    "change_management": (r"change management", r"adoption", r"implementation", r"zavádění do praxe", r"řízení změnových"),
    "leadership": (r"\blead(?:er|ership|ing)\b", r"director", r"head of"),
    "cross_functional_leadership": (r"cross.functional", r"lead.+team", r"build.+team", r"napříč firmou"),
    "cross_functional_work": (r"cross.functional", r"collaborative.+teams"),
    "executive_communication": (r"executive", r"communicat.+results", r"present.+leadership"),
    "business_operations": (r"business operations", r"operating model", r"operational", r"lidi v provozu", r"mapovat procesy"),
    "operating_model_design": (r"operating model", r"repeatable.+process", r"build.+function"),
    "customer_retention": (r"customer success", r"retention", r"customer lifecycle"),
    "commercial_strategy": (r"commercial strategy", r"go.to.market", r"strategic"),
    "strategy": (r"\bstrategy\b", r"strategic", r"hypotheses"),
    "experimentation": (r"experiment", r"hypotheses", r"testing methods"),
    "pricing_strategy": (r"pricing", r"price strategy"),
    "software_engineering_intensity": (r"software engineer", r"production code", r"SDK", r"systems engineering"),
    "software_engineering": (r"software engineer", r"software development", r"engineering practices"),
    "programming": (r"programming", r"production code", r"coding"),
    "production_software_development": (r"production", r"ship.+software", r"software development"),
    "sdk_development": (r"\bSDKs?\b",),
    "systems_engineering": (r"distributed systems", r"systems engineering", r"service reliability"),
    "python": (r"\bPython\b",),
    "sql": (r"\bSQL\b", r"relational databases?"),
    "mysql": (r"\bMySQL\b",),
    "data_engineering": (r"data engineering", r"data pipelines?", r"data flows?", r"data migrations?"),
    "etl_elt": (r"ETL/ELT", r"\bETL\b", r"\bELT\b"),
    "dbt": (r"\bdbt\b",),
    "airflow": (r"Airflow",),
    "machine_learning": (r"machine learning", r"\bML\b"),
    "deep_learning": (r"deep.learning",),
    "pytorch": (r"PyTorch",),
    "jax": (r"\bJAX\b",),
    "ml_research": (r"research scientist", r"ML research", r"drives research"),
    "model_training": (r"model training", r"train.+models?", r"learning architectures"),
    "robotics": (r"robotics", r"robotic"),
    "physical_ai": (r"physical AI", r"physical hardware"),
    "research_publications": (r"publications?",),
    "user_research_methodology": (r"user research", r"research methods", r"research methodology"),
    "conjoint_analysis": (r"conjoint",), "maxdiff": (r"MaxDiff",),
    "discrete_choice": (r"discrete choice",), "diary_studies": (r"diary stud",),
    "moderated_research": (r"moderated research",), "unmoderated_research": (r"unmoderated research",),
    "bachelors_degree": (r"Bachelor.s degree", r"bachelor degree"),
    "consulting_experience": (r"consulting experience", r"management consulting"),
    "direct_customer_success_practice": (r"customer success", r"CSM"),
    "b2b_enterprise_software": (r"enterprise software", r"B2B", r"enterprise customers"),
    "financial_services_domain": (r"financial services", r"financial crime", r"bank"),
    "fintech_domain": (r"fintech", r"financial crime"),
    "people_management_scope": (r"manage.+team", r"lead.+researchers", r"build.+team"),
    "quota_sales_responsibility": (r"sales quota", r"quota.carrying", r"revenue target"),
    "decentralized_decision_making": (r"decentrali[sz]ed", r"independent decisions", r"každý GM rozhoduje sám"),
}


def extract_features(job: SemanticJobInput, taxonomy: Taxonomy) -> tuple[DeterministicFeature, ...]:
    sources = {"title": job.title or "", "description": job.description}
    found: list[DeterministicFeature] = []
    for concept_id, patterns in CONCEPT_PATTERNS.items():
        taxonomy.require(concept_id, "feature concept")
        for source_field, value in sources.items():
            match = next((re.search(pattern, value, re.I | re.S) for pattern in patterns if re.search(pattern, value, re.I | re.S)), None)
            if match:
                start, end = max(0, match.start() - 45), min(len(value), match.end() + 70)
                evidence = re.sub(r"\s+", " ", value[start:end]).strip()
                found.append(DeterministicFeature(concept_id, evidence, source_field, RULE_VERSION))
                break
    return tuple(found)


def triage_score(features: tuple[DeterministicFeature, ...]) -> int:
    # Diagnostic density/order only; never an exclusion decision in Phase 3.
    broad = {item.concept_id for item in features}
    score = min(100, 10 + len(broad) * 4)
    if "ai_enabled_work" in broad:
        score += 5
    if broad & {"stakeholder_management", "analytical_problem_solving", "software_engineering", "ml_research"}:
        score += 5
    return min(100, score)
