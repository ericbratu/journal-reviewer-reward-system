import openreview
from typing import List, Dict, Any
import textwrap


class OpenReviewScraper:
    def __init__(self, venue: str = "ICLR.cc/2023/Conference"):
        self.venue = venue
        self.client = openreview.Client(baseurl="https://api.openreview.net")

    @staticmethod
    def pick(content: Dict, keys: List[str]) -> str:
        content = content or {}
        for k in keys:
            v = content.get(k, "")
            if isinstance(v, dict):
                v = v.get("value", "")
            if v:
                return v
        return ""

    @staticmethod
    def _notes_list(resp: Any) -> List[Any]:
        if resp is None:
            return []
        if isinstance(resp, list):
            return resp
        notes = getattr(resp, "notes", None)
        return notes if isinstance(notes, list) else []

    def _get_some_submissions(self, limit: int = 50) -> List[Any]:
        candidates = [
            f"{self.venue}/-/Blind_Submission",
            f"{self.venue}/-/Submission",
            f"{self.venue}/-/Paper",
        ]

        for inv in candidates:
            try:
                resp = self.client.get_notes(invitation=inv, limit=limit)
                notes = self._notes_list(resp)
                if notes:
                    print(f"Using submission invitation: {inv}")
                    return notes
            except TypeError:
                try:
                    resp = self.client.get_notes(invitation=inv)
                    notes = self._notes_list(resp)
                    if notes:
                        print(f"Using submission invitation (no limit supported): {inv}")
                        return notes[:limit]
                except Exception:
                    pass
            except Exception:
                pass

        raise RuntimeError(
            "Could not fetch submissions with common invitations."
        )

    def scrape_reviews(self, paper_limit: int = 50) -> List[Dict]:
        submissions = self._get_some_submissions(limit=paper_limit)
        print(f"Fetched {len(submissions)} submissions (testing)")

        dataset: List[Dict] = []

        for idx, sub in enumerate(submissions, 1):
            paper_id = getattr(sub, "id", None)
            if not paper_id:
                continue

            sub_content = getattr(sub, "content", {}) or {}
            title = self.pick(sub_content, ["title"])
            abstract = self.pick(sub_content, ["abstract"])

            try:
                forum_notes = self.client.get_notes(forum=paper_id)
                forum_notes = self._notes_list(forum_notes)
            except Exception:
                continue

            for n in forum_notes:
                inv = getattr(n, "invitation", "") or ""
                if not inv.endswith("/-/Official_Review"):
                    continue

                rc = getattr(n, "content", {}) or {}
                dataset.append({
                    "paper_id": paper_id,
                    "review_id": getattr(n, "id", None),
                    "title": title,
                    "abstract": abstract,
                    "review_text": self.pick(rc, ["review", "comments_to_authors", "main_review", "comments"]),
                    "summary": self.pick(rc, ["summary", "summary_of_the_paper", "paper_summary"]),
                    "strengths": self.pick(rc, ["strengths", "pros", "strong_points"]),
                    "weaknesses": self.pick(rc, ["weaknesses", "cons", "weak_points"]),
                    "rating": self.pick(rc, ["rating", "recommendation", "score", "overall_rating"]),
                })

            if idx % 10 == 0:
                print(f"Processed {idx}/{len(submissions)} papers... rows={len(dataset)}")

        return dataset


def pretty_print_dataset(dataset, max_papers=3):
    papers = {}

    for r in dataset:
        pid = r["paper_id"]
        papers.setdefault(pid, {
            "title": r["title"],
            "abstract": r["abstract"],
            "reviews": []
        })
        papers[pid]["reviews"].append(r)

    print("\n" + "=" * 80)
    print(f"Unique papers scraped: {len(papers)}")
    print("=" * 80)

    for i, (pid, paper) in enumerate(papers.items()):
        if i >= max_papers:
            break

        print(f"\nPAPER {i+1}")
        print("-" * 80)

        print("\nTITLE:")
        print(textwrap.fill(paper["title"], width=90))

        print("\nABSTRACT:")
        print(textwrap.fill(paper["abstract"], width=90))

        print(f"\nREVIEWS ({len(paper['reviews'])})")
        print("-" * 40)

        for j, review in enumerate(paper["reviews"]):
            print(f"\nReview {j+1}")
            print("Rating:", review["rating"] or "N/A")

            if review["summary"]:
                print("\nSummary:")
                print(textwrap.fill(review["summary"], width=90))

        print("\n" + "=" * 80)


def main():
    scraper = OpenReviewScraper("ICLR.cc/2023/Conference")
    dataset = scraper.scrape_reviews(paper_limit=50)

    print("\nDataset size:", len(dataset))
    if dataset:
        pretty_print_dataset(dataset, max_papers=3)
    else:
        print("\nNo reviews found.")


if __name__ == "__main__":
    main()
