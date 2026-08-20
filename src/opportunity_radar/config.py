from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


class ConfigurationError(ValueError):
    pass


@dataclass(frozen=True)
class CompanyConfig:
    company_id: str
    company_name: str
    adapter: str
    careers_url: str | None = None
    jobs_search_url: str | None = None
    ats_tenant: str | None = None
    endpoint_url: str | None = None
    location_filters: list[str] = field(default_factory=list)
    remote_eligible: bool | None = None
    options: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "CompanyConfig":
        known = {f.name for f in cls.__dataclass_fields__.values()}
        unknown = set(raw) - known
        if unknown:
            raise ConfigurationError(f"unknown company configuration keys: {sorted(unknown)}")
        try:
            config = cls(**raw)
        except TypeError as exc:
            raise ConfigurationError(str(exc)) from exc
        config.validate()
        return config

    def validate(self) -> None:
        if not self.company_id or not self.company_name or not self.adapter:
            raise ConfigurationError("company_id, company_name and adapter are required")
        if self.adapter == "greenhouse" and not self.ats_tenant:
            raise ConfigurationError(f"{self.company_id}: Greenhouse requires ats_tenant")
        if self.adapter == "workday":
            parts = (self.ats_tenant or "").split("|")
            if len(parts) != 3 or not all(parts):
                raise ConfigurationError(
                    f"{self.company_id}: Workday ats_tenant must be host|tenant|site"
                )
        if self.adapter in {"almacareer", "successfactors", "generic_html"} and not self.endpoint_url:
            raise ConfigurationError(f"{self.company_id}: {self.adapter} requires endpoint_url")
        if self.adapter == "generic_html" and not self.options.get("selectors") and not self.options.get("json_ld", True):
            raise ConfigurationError(
                f"{self.company_id}: generic_html requires selectors or json_ld"
            )


def load_companies(path: str | Path) -> list[CompanyConfig]:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or not isinstance(raw.get("companies"), list):
        raise ConfigurationError("configuration root must contain a companies list")
    companies = [CompanyConfig.from_dict(item) for item in raw["companies"]]
    ids = [company.company_id for company in companies]
    if len(ids) != len(set(ids)):
        raise ConfigurationError("company_id values must be unique")
    return companies

