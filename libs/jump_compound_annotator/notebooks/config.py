from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
OUTPUT_DIR = PROJECT_ROOT / "outputs"

# Constants
RELATIONSHIP_TYPE_MAPPING = {
    "DOWNREGULATES_CHdG": "downregulates",
    "CdG": "downregulates",
    "UPREGULATES_CHuG": "upregulates",
    "CuG": "upregulates",
    "DRUG_TARGET": "targets",
    "target": "targets",
    "DRUG_CARRIER": "carries",
    "carrier": "carries",
    "DRUG_ENZYME": "enzyme",
    "enzyme": "enzyme",
    "DRUG_TRANSPORTER": "transports",
    "transporter": "transports",
    "BINDS_CHbG": "binds",
    "CbG": "binds",
    "DRUG_BINDING_GENE": "binds",
}

EXCLUDED_RELATIONSHIPS = ["DPI", "DRUG_BINDINH_GENE"]
HUB_COMPOUND_THRESHOLD = 0.999  # 99.9th percentile for filtering hub compounds
