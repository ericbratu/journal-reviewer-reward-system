import openreview
import json
from pathlib import Path
from typing import List, Dict, Any
import textwrap


class OpenReviewScraper:
    def __init__(self, venue: str = "ICLR.cc/2023/Conference"):
        self.venue = venue
        self.client = openreview.Client(baseurl="https://api.openreview.net")
        api_module = getattr(openreview, "api", None)
        self.client_v2 = None
        if api_module is not None and hasattr(api_module, "OpenReviewClient"):
            self.client_v2 = api_module.OpenReviewClient(
                baseurl="https://api2.openreview.net"
            )
            print("Using public OpenReview API v2 client")
        else:
            print("OpenReview API v2 client unavailable, using API v1 fallback")

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

    def build_review_text(self, content: Dict) -> str:
        direct_review = self.pick(
            content,
            [
                "review",
                "comments_to_authors",
                "main_review",
                "comments",
            ],
        )
        if direct_review:
            return direct_review

        sections = []
        field_map = [
            ("summary", ["summary", "summary_of_the_paper", "paper_summary"]),
            ("strengths", ["strengths", "pros", "strong_points"]),
            ("weaknesses", ["weaknesses", "cons", "weak_points"]),
            ("questions", ["questions", "questions_for_authors"]),
            ("limitations", ["limitations"]),
        ]

        for label, keys in field_map:
            value = self.pick(content, keys)
            if value:
                sections.append(f"{label.capitalize()}:\n{value}")

        return "\n\n".join(sections)

    def _get_some_submissions(self, limit: int = 50) -> List[Any]:
        if self.client_v2 is not None:
            try:
                notes = self._get_some_submissions_v2(limit=limit)
                if notes:
                    print("Fetched submissions through public API v2")
                    return notes
                print("API v2 returned zero submissions, falling back to invitation queries")
            except Exception as exc:
                print(f"API v2 submission fetch failed: {type(exc).__name__}: {exc}")
                print("Falling back to hardcoded invitation queries on API v1")

        candidates = [
            f"{self.venue}/-/Blind_Submission",
            f"{self.venue}/-/Submission",
            f"{self.venue}/-/Paper",
        ]
        errors = []

        for inv in candidates:
            print(f"Trying submission invitation: {inv}")
            try:
                resp = self.client.get_notes(invitation=inv, limit=limit)
                notes = self._notes_list(resp)
                if notes:
                    print(f"Using submission invitation: {inv}")
                    return notes
                print(f"No submissions returned for invitation: {inv}")
            except TypeError:
                print(
                    f"Invitation {inv} does not support limit in this client version. "
                    "Retrying without limit."
                )
                try:
                    resp = self.client.get_notes(invitation=inv)
                    notes = self._notes_list(resp)
                    if notes:
                        print(f"Using submission invitation (no limit supported): {inv}")
                        return notes[:limit]
                    print(f"No submissions returned for invitation: {inv}")
                except Exception as exc:
                    errors.append((inv, exc))
                    print(f"Failed invitation {inv}: {type(exc).__name__}: {exc}")
            except Exception as exc:
                errors.append((inv, exc))
                print(f"Failed invitation {inv}: {type(exc).__name__}: {exc}")

        if errors:
            error_lines = [
                f"- {inv}: {type(exc).__name__}: {exc}" for inv, exc in errors
            ]
            details = "\n".join(error_lines)
        else:
            details = "- No exceptions were raised, but all invitations returned zero notes."
        raise RuntimeError(
            "Could not fetch submissions with common invitations.\n"
            f"Venue: {self.venue}\n"
            f"Tried:\n{details}"
        )

    def _get_some_submissions_v2(self, limit: int = 50) -> List[Any]:
        venue_candidates = [
            self.venue,
            f"{self.venue}/-/Submission",
            f"{self.venue}/-/Blind_Submission",
        ]

        errors = []
        for venue_id in venue_candidates:
            print(f"Trying API v2 venue query: {venue_id}")
            try:
                notes = self.client_v2.get_all_notes(content={"venueid": venue_id})
                notes = self._notes_list(notes)
                if notes:
                    return notes[:limit]
                print(f"No submissions returned for API v2 venue query: {venue_id}")
            except Exception as exc:
                errors.append((venue_id, exc))
                print(f"Failed API v2 venue query {venue_id}: {type(exc).__name__}: {exc}")

        if errors:
            error_lines = [
                f"- {venue_id}: {type(exc).__name__}: {exc}"
                for venue_id, exc in errors
            ]
            raise RuntimeError(
                "API v2 submission queries failed.\n" + "\n".join(error_lines)
            )
        return []

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
                forum_notes = self._get_forum_notes(paper_id)
            except Exception as exc:
                print(
                    f"Failed to fetch forum notes for paper {paper_id}: "
                    f"{type(exc).__name__}: {exc}"
                )
                continue

            for n in forum_notes:
                if not self._is_official_review_note(n):
                    continue

                rc = getattr(n, "content", {}) or {}
                dataset.append({
                    "paper_id": paper_id,
                    "review_id": getattr(n, "id", None),
                    "title": title,
                    "abstract": abstract,
                    "review_text": self.build_review_text(rc),
                    "summary": self.pick(rc, ["summary", "summary_of_the_paper", "paper_summary"]),
                    "strengths": self.pick(rc, ["strengths", "pros", "strong_points"]),
                    "weaknesses": self.pick(rc, ["weaknesses", "cons", "weak_points"]),
                    "rating": self.pick(rc, ["rating", "recommendation", "score", "overall_rating"]),
                })

            if idx % 10 == 0:
                print(f"Processed {idx}/{len(submissions)} papers... rows={len(dataset)}")

        return dataset

    def _get_forum_notes(self, paper_id: str) -> List[Any]:
        if self.client_v2 is not None:
            try:
                notes = self.client_v2.get_all_notes(forum=paper_id)
                notes = self._notes_list(notes)
                if notes:
                    return notes
            except Exception as exc:
                print(
                    f"API v2 forum fetch failed for {paper_id}: "
                    f"{type(exc).__name__}: {exc}"
                )

        notes = self.client.get_notes(forum=paper_id)
        return self._notes_list(notes)

    def _is_official_review_note(self, note: Any) -> bool:
        invitation = (getattr(note, "invitation", "") or "").lower()
        if invitation.endswith("/-/official_review"):
            return True

        content = getattr(note, "content", {}) or {}
        field_names = {str(key).lower() for key in content.keys()}
        reviewish_fields = {
            "review",
            "main_review",
            "comments_to_authors",
            "summary",
            "strengths",
            "weaknesses",
            "rating",
        }
        return bool(field_names.intersection(reviewish_fields))


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
    import argparse

    parser = argparse.ArgumentParser(description="Fetch peer reviews from OpenReview")
    parser.add_argument(
        "--conference",
        type=str,
        default="ICLR",
        help="Conference short name (e.g., ICLR, NeurIPS, ACL).",
    )
    parser.add_argument(
        "--year",
        type=int,
        default=2023,
        help="Conference year.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Number of submissions to inspect.",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="data/raw",
        help="Output directory for JSON data.",
    )
    parser.add_argument(
        "--pretty_print",
        action="store_true",
        help="Print sample papers and reviews.",
    )
    args = parser.parse_args()

    venue = f"{args.conference}.cc/{args.year}/Conference"
    scraper = OpenReviewScraper(venue)
    dataset = scraper.scrape_reviews(paper_limit=args.limit)

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"{args.conference.lower()}_{args.year}.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(dataset, f, indent=2, ensure_ascii=False)

    print(f"\nSaved {len(dataset)} reviews to {output_file}")

    if args.pretty_print:
        if dataset:
            pretty_print_dataset(dataset, max_papers=3)
        else:
            print("\nNo reviews found.")


if __name__ == "__main__":
    main()
