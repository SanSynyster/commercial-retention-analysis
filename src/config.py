from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"


@dataclass(frozen=True)
class DatasetConfig:
    """Configuration for a supported raw dataset version."""

    name: str
    raw_path: Path
    processed_dir: Path
    description: str


DATASETS: dict[str, DatasetConfig] = {
    "v1": DatasetConfig(
        name="v1",
        raw_path=RAW_DIR / "Online Retail.xlsx",
        processed_dir=PROCESSED_DIR / "v1_online_retail",
        description="Original one-year UCI Online Retail workbook",
    ),
    "v2": DatasetConfig(
        name="v2",
        raw_path=RAW_DIR / "online_retail_II.csv",
        processed_dir=PROCESSED_DIR / "v2_online_retail_ii",
        description="Expanded two-year Online Retail II CSV",
    ),
}


def get_dataset_config(dataset: str, processed_dir: str | Path | None = None) -> DatasetConfig:
    """Return dataset configuration, optionally overriding the output directory."""

    try:
        config = DATASETS[dataset]
    except KeyError as exc:
        supported = ", ".join(sorted(DATASETS))
        raise ValueError(f"Unsupported dataset '{dataset}'. Supported datasets: {supported}") from exc

    if processed_dir is None:
        return config

    return DatasetConfig(
        name=config.name,
        raw_path=config.raw_path,
        processed_dir=Path(processed_dir),
        description=config.description,
    )
