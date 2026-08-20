from __future__ import annotations

from opportunity_radar.models import NormalizedJob

from .generic import GenericHtmlAdapter


class SuccessFactorsAdapter(GenericHtmlAdapter):
    """Declarative adapter for public SuccessFactors career sites."""

    source = "successfactors"

    def fetch_job(self, job_reference) -> NormalizedJob:
        job = super().fetch_job(job_reference)
        return NormalizedJob(**{**job.__dict__, "source": self.source})

