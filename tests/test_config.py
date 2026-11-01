from pathlib import Path

from stroomprijsvoorspeller.config import load_config

ROOT = Path(__file__).resolve().parents[1]


def test_config_laadt_en_is_consistent():
    cfg = load_config(ROOT / "config.yaml")
    assert cfg.biedzone == "NL"
    assert cfg.kwantielen == (0.1, 0.5, 0.9)
    assert cfg.horizon_dagen == (2, 3, 4, 5, 6, 7)
    assert max(cfg.horizon_dagen) <= max(cfg.lead_dagen), "voor elke horizon moet een weer-lead bestaan"
    assert len({p.naam for p in cfg.weerpunten}) == len(cfg.weerpunten)
    assert cfg.raw_dir == ROOT / "data" / "raw"
    assert all(50 < p.lat < 56 and 2 < p.lon < 10 for p in cfg.weerpunten)
