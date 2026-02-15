import json
from pathlib import Path
from typing import Optional, Dict, List


class ReviewDataset:

    def __init__(self, data_path: str, miner_id: int):
        self.data_path = Path(data_path)
        self.miner_id = miner_id
        self.current_index = 0

        review_file = self.data_path / f"miner_{miner_id}_reviews.json"

        if not review_file.exists():
            print(f"Warning: {review_file} not found. Run data preprocessing first.")
            self.reviews: List[Dict] = []
        else:
            with open(review_file, "r", encoding="utf-8") as f:
                self.reviews = json.load(f)
            print(f"Miner {miner_id}: loaded {len(self.reviews)} reviews")

    def get_next(self) -> Optional[Dict]:
        if not self.reviews:
            return None
        review = self.reviews[self.current_index]
        self.current_index = (self.current_index + 1) % len(self.reviews)
        return review

    def get_review_for_paper(self, paper_id: str) -> Optional[Dict]:
        for review in self.reviews:
            if review["paper_id"] == paper_id:
                return review
        return None

    def __len__(self) -> int:
        return len(self.reviews)
