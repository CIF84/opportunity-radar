from __future__ import annotations

from opportunity_radar.models import NormalizedJob

from .generic import GenericHtmlAdapter


class AlmaCareerAdapter(GenericHtmlAdapter):
    """Declarative adapter for branded Jobs.cz/Alma Career portals."""

    source = "almacareer"

    def fetch_job(self, job_reference) -> NormalizedJob:
        job = super().fetch_job(job_reference)
        return NormalizedJob(**{**job.__dict__, "source": self.source})

