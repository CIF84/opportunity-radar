import pytest

from opportunity_radar.config import CompanyConfig, ConfigurationError
from opportunity_radar.registry import AdapterRegistry


def test_registry_maps_only_adapter_family():
    config = CompanyConfig("acme", "Acme", "greenhouse", ats_tenant="acme")
    assert AdapterRegistry.create(config).source == "greenhouse"


def test_registry_rejects_unknown_family():
    config = CompanyConfig("acme", "Acme", "bespoke")
    with pytest.raises(ConfigurationError, match="unknown adapter"):
        AdapterRegistry.create(config)

