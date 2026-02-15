import json
import hashlib
import numpy as np
from pathlib import Path
from typing import List, Dict, Tuple, Optional
import bittensor as bt

try:
    from openai import AsyncOpenAI
except ImportError:
    AsyncOpenAI = None


RUBRIC_SYSTEM_PROMPT = """You are an expert peer review evaluator for academic conferences.

Your task is to evaluate the quality of peer reviews using a structured rubric.

Evaluate each review on these criteria (0-5 scale each):

1. **Comprehension** (0-5): Does the reviewer demonstrate understanding of the paper's core contributions?
   - 0: No understanding evident
   - 3: Basic understanding
   - 5: Deep, nuanced understanding

2. **Technical Depth** (0-5): Does the review engage with technical details and methodology?
   - 0: Purely superficial
   - 3: Some technical engagement
   - 5: Rigorous technical analysis

3. **Specificity** (0-5): Are criticisms and praise specific with examples?
   - 0: Vague generalities only
   - 3: Mix of specific and general
   - 5: Highly specific throughout

4. **Constructiveness** (0-5): Does the review help authors improve the work?
   - 0: Purely negative or unhelpful
   - 3: Some actionable feedback
   - 5: Clear, actionable suggestions

5. **Evidence-Based** (0-5): Are claims supported by evidence from the paper?
   - 0: Unsupported assertions
   - 3: Some evidence provided
   - 5: All claims well-supported

6. **Professionalism** (0-5): Is the tone respectful and appropriate?
   - 0: Unprofessional or hostile
   - 3: Generally professional
   - 5: Exemplary professionalism

Return your evaluation as JSON with this exact structure:
{
  "comprehension": <0-5>,
  "technical_depth": <0-5>,
  "specificity": <0-5>,
  "constructiveness": <0-5>,
  "evidence_based": <0-5>,
  "professionalism": <0-5>,
  "justification": "<brief explanation of scores>",
  "confidence": <0.0-1.0>
}

Be rigorous. Most reviews should score 2-3. Scores of 5 are rare and must be earned."""


CRITERIA = [
    "comprehension",
    "technical_depth",
    "specificity",
    "constructiveness",
    "evidence_based",
    "professionalism",
]

CRITERIA_WEIGHTS = {
    "comprehension": 0.20,
    "technical_depth": 0.25,
    "specificity": 0.20,
    "constructiveness": 0.15,
    "evidence_based": 0.15,
    "professionalism": 0.05,
}


class LLMReviewScorer:

    def __init__(
        self,
        model: str = "gpt-4.1-mini",
        api_key: Optional[str] = None,
        cache_dir: str = "data/cache",
        temperature: float = 0.0,
    ):
        if AsyncOpenAI is None:
            raise ImportError("openai not installed. Run: pip install openai")

        self.model = model
        self.temperature = temperature
        self.client = AsyncOpenAI(api_key=api_key)

        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        bt.logging.info(f"Initialized LLM scorer with model: {model}")

    def _cache_key(self, paper_abstract: str, review_text: str) -> str:
        content = f"{self.model}|{paper_abstract}|{review_text}"
        return hashlib.sha256(content.encode()).hexdigest()

    def _get_cached(self, cache_key: str) -> Optional[Dict]:
        cache_file = self.cache_dir / f"{cache_key}.json"
        if cache_file.exists():
            with open(cache_file, "r") as f:
                return json.load(f)
        return None

    def _save_cache(self, cache_key: str, score_data: Dict):
        cache_file = self.cache_dir / f"{cache_key}.json"
        with open(cache_file, "w") as f:
            json.dump(score_data, f, indent=2)

    async def score_review(
        self,
        paper_abstract: str,
        review_text: str,
        use_cache: bool = True,
    ) -> Dict:
        if use_cache:
            cache_key = self._cache_key(paper_abstract, review_text)
            cached = self._get_cached(cache_key)
            if cached is not None:
                bt.logging.debug("Using cached score")
                return cached

        user_prompt = (
            f"Paper Abstract:\n{paper_abstract[:1000]}\n\n"
            f"Review to Evaluate:\n{review_text[:3000]}\n\n"
            f"Evaluate this review using the rubric."
        )

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": RUBRIC_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=self.temperature,
                response_format={"type": "json_object"},
            )
            result = json.loads(response.choices[0].message.content)
            score_data = self._validate_and_aggregate(result)

            if use_cache:
                self._save_cache(cache_key, score_data)

            return score_data

        except Exception as e:
            bt.logging.error(f"Error scoring review: {e}")
            return {
                c: 0 for c in CRITERIA
            } | {
                "justification": f"Error during scoring: {str(e)}",
                "confidence": 0.0,
                "aggregate_score": 0.0,
                "error": str(e),
            }

    def _validate_and_aggregate(self, result: Dict) -> Dict:
        for criterion in CRITERIA:
            if criterion not in result:
                result[criterion] = 0
            else:
                result[criterion] = max(0, min(5, float(result[criterion])))

        if "confidence" not in result:
            result["confidence"] = 0.5
        else:
            result["confidence"] = max(0.0, min(1.0, float(result["confidence"])))

        aggregate = sum(
            result[criterion] * CRITERIA_WEIGHTS[criterion] * 20
            for criterion in CRITERIA
        )
        result["aggregate_score"] = aggregate

        return result

    async def score_reviews_for_paper(
        self,
        paper_abstract: str,
        reviews: List[Dict],
    ) -> List[Dict]:
        scores = []
        for review in reviews:
            review_text = review.get("review_text", "")
            if not review_text:
                bt.logging.warning("Empty review text, assigning zero score")
                scores.append({
                    "aggregate_score": 0.0,
                    "confidence": 0.0,
                    "error": "Empty review",
                })
                continue
            score = await self.score_review(paper_abstract, review_text)
            scores.append(score)
        return scores


async def score_reviews_grouped(
    validator,
    responses: List,
) -> Tuple[np.ndarray, List[int]]:
    model = getattr(validator.config, "llm_model", "gpt-4.1-mini")
    scorer = LLMReviewScorer(model=model)

    data_path = getattr(validator.config, "data_path", "data/processed")
    metadata_file = Path(data_path) / "paper_metadata.json"

    if metadata_file.exists():
        with open(metadata_file, "r") as f:
            paper_metadata = json.load(f)
    else:
        paper_metadata = {}
        bt.logging.warning("No paper metadata found, using empty abstracts")

    reviews_by_paper: Dict[str, List[Dict]] = {}
    for i, response in enumerate(responses):
        if response.paper_id is None:
            continue
        reviews_by_paper.setdefault(response.paper_id, []).append({
            "miner_uid": i,
            "review_text": response.review_text,
            "synapse": response,
        })

    all_rewards = np.zeros(len(responses))

    for paper_id, paper_reviews in reviews_by_paper.items():
        paper_info = paper_metadata.get(paper_id, {})
        abstract = paper_info.get("abstract", "")

        if not abstract:
            bt.logging.warning(f"No abstract for paper {paper_id}, using title only")
            abstract = paper_info.get("title", "Unknown paper")

        scores = await scorer.score_reviews_for_paper(abstract, paper_reviews)

        ranked_indices = np.argsort(
            [s["aggregate_score"] for s in scores]
        )[::-1]

        for rank, idx in enumerate(ranked_indices):
            miner_uid = paper_reviews[idx]["miner_uid"]
            base_score = scores[idx]["aggregate_score"]
            confidence = scores[idx].get("confidence", 1.0)

            reward = base_score * np.exp(-0.5 * rank) * confidence
            all_rewards[miner_uid] = reward

            paper_reviews[idx]["synapse"].review_score = scores[idx]
            paper_reviews[idx]["synapse"].final_score = reward

    if all_rewards.max() > 0:
        all_rewards = all_rewards / all_rewards.max()

    miner_uids = list(range(len(responses)))
    return all_rewards, miner_uids
