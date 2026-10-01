"""Stage 1: Classification of affected economic branches/sectors.

Supports:
- Multilingual Zero-Shot NLI (via Transformers: MoritzLaurer/multilingual-MiniLMv2-L6-mnli-xnli or mDeBERTa-v3)
- Keyword heuristic fallback (offline / fast / when transformers is not installed)
- Seamless interface returning List[BranchHit]
"""
import json
import logging
import re
from pathlib import Path
from typing import List, Optional, Dict, Union
from src.models import BranchHit

logger = logging.getLogger(__name__)

_BRANCHES_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "branches.json"

ALL_BRANCHES: List[str] = [
    "energy", "finance", "tech", "agro", "logistics",
    "defense", "pharma", "metals", "realty", "retail"
]

BRANCH_PRESETS: Dict[str, List[str]] = {
    "all": ALL_BRANCHES,
    "forex": ["finance"],
    "fx": ["finance"],
    "finance": ["finance"],
    "crypto": ["finance", "tech"],
    "commodities": ["energy", "metals", "agro"],
    "macro": ["finance", "energy"],
    "industry": ["logistics", "metals", "energy"],
}


def resolve_branches(raw: Optional[Union[str, List[str]]]) -> Optional[List[str]]:
    """Resolves branch names or preset identifiers into a canonical list of branch IDs.

    Returns None if all branches should be evaluated (no restriction).
    """
    if not raw:
        return None

    if isinstance(raw, str):
        parts = [p.strip().lower() for p in raw.split(",") if p.strip()]
    elif isinstance(raw, (list, tuple, set)):
        parts = [str(p).strip().lower() for p in raw if str(p).strip()]
    else:
        return None

    if not parts or "all" in parts:
        return None

    resolved = []
    for p in parts:
        if p in BRANCH_PRESETS:
            for b in BRANCH_PRESETS[p]:
                if b not in resolved:
                    resolved.append(b)
        elif p in ALL_BRANCHES:
            if p not in resolved:
                resolved.append(p)
        else:
            logger.warning(
                f"Unknown topic/branch: '{p}'. Ignored. Available: {ALL_BRANCHES + list(BRANCH_PRESETS.keys())}"
            )

    return resolved if resolved else None


# Semantic description labels for multilingual Zero-Shot NLI
BRANCH_LABEL_MAP: Dict[str, str] = {
    "energy": "energy, oil, gas, fuel and power grid",
    "finance": "finance, banking, forex, currencies, stock market, interest rates and economy",
    "tech": "technology, artificial intelligence, software and semiconductors",
    "agro": "agriculture, grain, crops and fertilizers",
    "logistics": "logistics, shipping, transport, airlines and supply chain",
    "defense": "defense, military, armed forces, weapons and security",
    "pharma": "pharmaceuticals, healthcare, medicine and biotechnology",
    "metals": "metals, mining, steel, gold and commodities",
    "realty": "real estate, housing, construction and mortgages",
    "retail": "retail, e-commerce, consumer goods and shopping",
}


def _load_branches():
    with open(_BRANCHES_PATH, encoding="utf-8") as f:
        return json.load(f)


def _kw_pattern(kw: str) -> str:
    kw = kw.strip().lower()
    if not kw:
        return ""
    if " " in kw or len(kw) <= 4:
        return r"\b" + re.escape(kw) + r"\b"
    return r"\b" + re.escape(kw) + r"\w*"


class BranchClassifier:
    def __init__(
        self,
        threshold: int = 1,
        max_branches: int = 3,
        use_transformers: bool = True,
        model_name: str = "MoritzLaurer/multilingual-MiniLMv2-L6-mnli-xnli",
        min_confidence: float = 0.35,
        allowed_branches: Optional[Union[str, List[str]]] = None,
    ):
        self.data = _load_branches()
        self.threshold = threshold
        self.max_branches = max_branches
        self.use_transformers = use_transformers
        self.model_name = model_name
        self.min_confidence = min_confidence

        resolved = resolve_branches(allowed_branches)
        self.allowed_branches = set(resolved) if resolved else None

        self._nlp_pipeline = None
        self._transformer_failed = False

    def _init_transformer(self):
        if not self.use_transformers or self._transformer_failed:
            return
        if self._nlp_pipeline is None:
            try:
                from transformers import pipeline
                logger.info(f"Loading Zero-Shot Branch model: {self.model_name}")
                self._nlp_pipeline = pipeline(
                    "zero-shot-classification",
                    model=self.model_name,
                    device=-1  # default to CPU for portability
                )
            except Exception as e:
                logger.warning(f"Could not load transformer model {self.model_name}: {e}. Falling back to keywords.")
                self._transformer_failed = True

    def classify_keywords(self, title: str, text: str) -> List[BranchHit]:
        blob = f"{title} {text}".lower()
        scored = []
        for branch, cfg in self.data.items():
            if self.allowed_branches and branch not in self.allowed_branches:
                continue
            kws = [k.lower().strip() for k in cfg.get("keywords_ru", []) + cfg.get("keywords_en", [])]
            matched = []
            for k in kws:
                pat = _kw_pattern(k)
                if pat and re.search(pat, blob):
                    matched.append(k)
            if len(matched) >= self.threshold:
                conf = min(0.95, 0.4 + 0.15 * len(matched))
                scored.append(BranchHit(branch=branch, confidence=round(conf, 2), matched_keywords=matched[:5]))
        scored.sort(key=lambda x: x.confidence, reverse=True)
        return scored[: self.max_branches]

    def classify_transformer(self, title: str, text: str) -> Optional[List[BranchHit]]:
        self._init_transformer()
        if self._nlp_pipeline is None:
            return None

        content = f"{title}. {text}".strip()
        if not content:
            return []

        # Candidate descriptions: filter if allowed_branches is specified
        if self.allowed_branches:
            target_labels = {
                b: desc for b, desc in BRANCH_LABEL_MAP.items()
                if b in self.allowed_branches
            }
        else:
            target_labels = BRANCH_LABEL_MAP

        candidate_descriptions = list(target_labels.values())
        desc_to_branch = {desc: branch for branch, desc in target_labels.items()}

        try:
            # Multi-label classification: each branch is scored independently (sigmoid)
            result = self._nlp_pipeline(
                content[:512],
                candidate_labels=candidate_descriptions,
                multi_label=True
            )

            hits = []
            for label_desc, score in zip(result["labels"], result["scores"]):
                if score >= self.min_confidence:
                    branch_key = desc_to_branch[label_desc]
                    hits.append(
                        BranchHit(
                            branch=branch_key,
                            confidence=round(float(score), 2),
                            matched_keywords=[f"nli:{round(float(score), 2)}"]
                        )
                    )

            hits.sort(key=lambda x: x.confidence, reverse=True)
            return hits[: self.max_branches]
        except Exception as e:
            logger.warning(f"Transformer classification failed: {e}. Falling back to keywords.")
            return None

    def classify(self, title: str, text: str, lang: str = "") -> List[BranchHit]:
        if self.use_transformers:
            hits = self.classify_transformer(title, text)
            if hits is not None:
                # If zero-shot produced no hits above threshold, try keyword fallback
                if not hits:
                    return self.classify_keywords(title, text)
                return hits

        return self.classify_keywords(title, text)
