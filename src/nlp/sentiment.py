
from typing import List, Dict

def _try_finbert():
    try:
        from transformers import AutoTokenizer, AutoModelForSequenceClassification, pipeline
        model = "ProsusAI/finbert"
        tok = AutoTokenizer.from_pretrained(model)
        mdl = AutoModelForSequenceClassification.from_pretrained(model)
        clf = pipeline("sentiment-analysis", model=mdl, tokenizer=tok, truncation=True)
        return clf
    except Exception:
        return None

def _vader():
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
    return SentimentIntensityAnalyzer()

class SentimentScorer:
    def __init__(self):
        self.finbert = _try_finbert()
        if not self.finbert:
            self.vader = _vader()
        else:
            self.vader = None

    def score_texts(self, texts: List[str]) -> List[Dict]:
        out = []
        if self.finbert:
            preds = self.finbert(texts)
            for t, p in zip(texts, preds):
                label = p["label"].lower()
                score = p["score"]
                signed = score if "positive" in label else (-score if "negative" in label else 0.0)
                out.append({"text": t, "label": label, "score": signed})
        else:
            for t in texts:
                vs = self.vader.polarity_scores(t)
                out.append({"text": t, "label": "compound", "score": vs["compound"]})
        return out
