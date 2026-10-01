"""Stage 2: Impact assessment on affected branches.

Supports:
- English Financial Sentiment via ProsusAI/finbert
- Russian Financial Sentiment via mxlcw/rubert-tiny2-russian-financial-sentiment
- Keyword and heuristic fallback (offline / fast / when transformers is not installed)
- Seamless output of List[ImpactHit] with direction, magnitude, score, and explanation
"""
import logging
from typing import List, Optional
from src.models import BranchHit, ImpactHit

logger = logging.getLogger(__name__)

POS_RU = ["рост", "прибыл", "рекорд", "укрепл", "расшир", "запуск", "сделк", "одобр", "субсиди", "снижение ставки", "профицит"]
NEG_RU = ["паден", "убыт", "санкци", "дефицит", "банкрот", "авария", "срыв", "повышение ставки", "штраф", "замедлен", "обвал", "атака"]

POS_EN = ["surge", "record", "profit", "growth", "approval", "deal", "launch", "upgrade", "stimulus", "rate cut", "surplus"]
NEG_EN = ["drop", "plunge", "loss", "sanction", "deficit", "bankrupt", "fine", "downgrade", "slowdown", "attack", "rate hike", "crash"]

STRONG = ["рекорд", "обвал", "кризис", "прорыв", "record", "crash", "crisis", "breakthrough", "surge", "plunge"]


class ImpactClassifier:
    def __init__(
        self,
        use_transformers: bool = True,
        en_model: str = "ProsusAI/finbert",
        ru_model: str = "mxlcw/rubert-tiny2-russian-financial-sentiment",
    ):
        self.use_transformers = use_transformers
        self.en_model = en_model
        self.ru_model = ru_model

        self._pipeline_en = None
        self._pipeline_ru = None
        self._transformer_failed = False

    def _init_transformers(self):
        if not self.use_transformers or self._transformer_failed:
            return
        if self._pipeline_en is None and self._pipeline_ru is None:
            try:
                import torch
                from transformers import pipeline

                device = "mps" if torch.backends.mps.is_available() else -1

                logger.info(f"Loading EN Impact Model: {self.en_model}")
                self._pipeline_en = pipeline(
                    "text-classification",
                    model=self.en_model,
                    device=device,
                    top_k=None,
                    truncation=True,
                    max_length=512,
                )

                logger.info(f"Loading RU Impact Model: {self.ru_model}")
                self._pipeline_ru = pipeline(
                    "text-classification",
                    model=self.ru_model,
                    device=device,
                    top_k=None,
                    truncation=True,
                    max_length=512,
                )
            except Exception as e:
                logger.warning(f"Could not initialize transformer impact classifiers: {e}. Using rule-based fallback.")
                self._transformer_failed = True

    def classify_keywords(self, title: str, text: str, branches: List[BranchHit]) -> List[ImpactHit]:
        blob = f"{title} {text}".lower()
        pos = sum(1 for w in POS_RU + POS_EN if w.lower() in blob)
        neg = sum(1 for w in NEG_RU + NEG_EN if w.lower() in blob)

        if pos == 0 and neg == 0:
            score = 0.0
        else:
            score = (pos - neg) / max(1, (pos + neg))
        score = round(max(-1.0, min(1.0, score)), 2)

        if score > 0.15:
            direction = "positive"
        elif score < -0.15:
            direction = "negative"
        else:
            direction = "neutral"

        strong_hit = any(s.lower() in blob for s in STRONG)
        total = pos + neg
        if strong_hit or total >= 4:
            magnitude = "high"
        elif total >= 2:
            magnitude = "medium"
        else:
            magnitude = "low"

        out = []
        for b in branches:
            expl = f"keywords(pos={pos}, neg={neg})"
            out.append(
                ImpactHit(
                    branch=b.branch,
                    direction=direction,
                    magnitude=magnitude,
                    score=score,
                    explanation=expl,
                )
            )
        return out

    def classify_transformer(
        self, title: str, text: str, branches: List[BranchHit], lang: str
    ) -> Optional[List[ImpactHit]]:
        self._init_transformers()

        pipe = self._pipeline_ru if lang == "ru" else self._pipeline_en
        if pipe is None:
            return None

        content = f"{title}. {text}".strip()
        if not content:
            return []

        try:
            preds = pipe(content[:512])[0]
            scores_by_label = {p["label"].lower(): float(p["score"]) for p in preds}

            pos_prob = scores_by_label.get("positive", 0.0)
            neg_prob = scores_by_label.get("negative", 0.0)
            neu_prob = scores_by_label.get("neutral", 0.0)

            # Determine dominant label and composite score (-1..1)
            score = round(pos_prob - neg_prob, 2)
            if pos_prob > neg_prob and pos_prob > neu_prob:
                direction = "positive"
            elif neg_prob > pos_prob and neg_prob > neu_prob:
                direction = "negative"
            else:
                direction = "neutral"

            # Magnitude calculation
            blob = content.lower()
            strong_hit = any(s.lower() in blob for s in STRONG)
            dominant_prob = max(pos_prob, neg_prob, neu_prob)

            if strong_hit or dominant_prob >= 0.85:
                magnitude = "high"
            elif dominant_prob >= 0.60:
                magnitude = "medium"
            else:
                magnitude = "low"

            model_name = self.ru_model if lang == "ru" else self.en_model
            model_short = model_name.split("/")[-1]
            expl = f"{model_short}: {direction} (pos={pos_prob:.2f}, neg={neg_prob:.2f}, neu={neu_prob:.2f})"

            out = []
            for b in branches:
                out.append(
                    ImpactHit(
                        branch=b.branch,
                        direction=direction,
                        magnitude=magnitude,
                        score=score,
                        explanation=expl,
                    )
                )
            return out
        except Exception as e:
            logger.warning(f"Transformer impact classification failed: {e}. Falling back.")
            return None

    def classify(
        self, title: str, text: str, branches: List[BranchHit], lang: str = "en"
    ) -> List[ImpactHit]:
        if self.use_transformers:
            hits = self.classify_transformer(title, text, branches, lang)
            if hits is not None:
                return hits

        return self.classify_keywords(title, text, branches)
