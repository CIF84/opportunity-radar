from __future__ import annotations

from opportunity_radar.adapters import (
    AlmaCareerAdapter,
    GenericHtmlAdapter,
    GreenhouseAdapter,
    SuccessFactorsAdapter,
    WorkdayAdapter,
)
from opportunity_radar.adapters.base import JobSourceAdapter
from opportunity_radar.config import CompanyConfig, ConfigurationError


class AdapterRegistry:
    _adapters: dict[str, type[JobSourceAdapter]] = {
        "workday": WorkdayAdapter,
        "greenhouse": GreenhouseAdapter,
        "almacareer": AlmaCareerAdapter,
        "successfactors": SuccessFactorsAdapter,
        "generic_html": GenericHtmlAdapter,
    }

    @classmethod
    def create(cls, config: CompanyConfig) -> JobSourceAdapter:
        try:
            adapter = cls._adapters[config.adapter]
        except KeyError as exc:
            raise ConfigurationError(f"unknown adapter: {config.adapter}") from exc
        return adapter(config)

