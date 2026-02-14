import json
from pathlib import Path
from typing import List, Dict


class ReviewDataPreprocessor:
    """
    Takes flat review list from OpenReviewScraper and splits it into
    per-miner JSON files + paper metadata for the validator.
    """

    def __init__(self, reviews: List[Dict]):
        self.reviews = reviews

    @classmethod
    def from_json(cls, path: str) -> "ReviewDataPreprocessor":
        with open(path, "r", encoding="utf-8") as f:
            return cls(json.load(f))

    def process(self, output_dir: str, num_miners: int = 5):
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)

        # Build paper metadata (validator needs abstracts for scoring context)
        paper_metadata: Dict[str, Dict] = {}
        for r in self.reviews:
            pid = r["paper_id"]
            if pid not in paper_metadata:
                paper_metadata[pid] = {
                    "paper_id": pid,
                    "title": r.get("title", ""),
                    "abstract": r.get("abstract", ""),
                }

        # Round-robin assign reviews to miners
        miner_buckets: List[List[Dict]] = [[] for _ in range(num_miners)]
        for i, r in enumerate(self.reviews):
            miner_buckets[i % num_miners].append(r)

        # Write per-miner files
        for mid, bucket in enumerate(miner_buckets):
            with open(out / f"miner_{mid}_reviews.json", "w", encoding="utf-8") as f:
                json.dump(bucket, f, indent=2, ensure_ascii=False)

        # Write paper metadata
        with open(out / "paper_metadata.json", "w", encoding="utf-8") as f:
            json.dump(paper_metadata, f, indent=2, ensure_ascii=False)

        # Write summary
        summary = {
            "num_miners": num_miners,
            "total_reviews": len(self.reviews),
            "total_papers": len(paper_metadata),
            "reviews_per_miner": [len(b) for b in miner_buckets],
        }
        with open(out / "miner_assignments.json", "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)

        print(f"Processed {len(self.reviews)} reviews across {len(paper_metadata)} papers for {num_miners} miners")
        print(f"Output: {out}")
        return summary


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Preprocess scraped reviews for miners")
    parser.add_argument("--input", type=str, required=True, help="Path to scraped reviews JSON")
    parser.add_argument("--output", type=str, default="data/processed", help="Output directory")
    parser.add_argument("--num_miners", type=int, default=5, help="Number of miners to split across")
    args = parser.parse_args()

    preprocessor = ReviewDataPreprocessor.from_json(args.input)
    preprocessor.process(args.output, args.num_miners)
