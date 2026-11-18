"""Demo data: the web app's mock datasets loaded into the database (`umi-api seed`)."""

from umi_api.seed.loader import SeedReport, seed_demo
from umi_api.seed.mock_data import load_mock_data

__all__ = ["SeedReport", "load_mock_data", "seed_demo"]
