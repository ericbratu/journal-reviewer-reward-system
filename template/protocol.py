# The MIT License (MIT)
# Copyright © 2023 Yuma Rao
# TODO(developer): Set your name
# Copyright © 2023 <your name>

# Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
# documentation files (the “Software”), to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
# and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all copies or substantial portions of
# the Software.

# THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
# THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
# DEALINGS IN THE SOFTWARE.

import typing
import bittensor as bt

# Protocol for journal review quality evaluation subnet
# Miners submit historical peer reviews from OpenReview
# Validators score review quality using LLM-based rubric evaluation

# ---- miner ----
# Example usage:
#   def submit_review(synapse: ReviewSubmission) -> ReviewSubmission:
#       review_data = load_next_review()
#       synapse.paper_id = review_data['paper_id']
#       synapse.review_text = review_data['review_text']
#       return synapse
#   axon = bt.axon().attach(submit_review).serve(netuid=...).start()

# ---- validator ---
# Example usage:
#   dendrite = bt.dendrite()
#   responses = dendrite.query(ReviewSubmission(current_paper_id="paper_123"))
#   scores = evaluate_reviews(responses)


class ReviewSubmission(bt.Synapse):
    """
    Protocol for submitting and evaluating peer review quality.
    
    Miners submit historical reviews from OpenReview dataset.
    Validators score reviews using structured LLM rubric.
    
    Attributes:
    - current_paper_id: Paper ID that validator is requesting reviews for (validator sets)
    - paper_id: Paper ID for the submitted review (miner fills)
    - review_text: Full text of the peer review (miner fills)
    - review_metadata: Additional context about the review (miner fills)
    - review_score: Structured rubric scores from LLM evaluation (validator fills)
    - final_score: Aggregated quality score 0-100 (validator fills)
    """

    # Validator request: which paper to submit reviews for
    current_paper_id: typing.Optional[str] = None

    # Miner response: review submission
    paper_id: typing.Optional[str] = None
    review_text: typing.Optional[str] = None
    review_metadata: typing.Optional[dict] = None

    # Validator evaluation results
    review_score: typing.Optional[dict] = None
    final_score: typing.Optional[float] = None

    def deserialize(self) -> typing.Optional[dict]:
        """
        Deserialize the review submission. Returns the complete review data
        including metadata and scores if available.

        Returns:
        - dict: Complete review data with all fields, or None if no review submitted.

        Example:
        >>> synapse = ReviewSubmission(current_paper_id="paper_123")
        >>> synapse.paper_id = "paper_123"
        >>> synapse.review_text = "This paper presents..."
        >>> synapse.deserialize()
        {'paper_id': 'paper_123', 'review_text': 'This paper presents...', ...}
        """
        if self.paper_id is None:
            return None
            
        return {
            "paper_id": self.paper_id,
            "review_text": self.review_text,
            "review_metadata": self.review_metadata,
            "review_score": self.review_score,
            "final_score": self.final_score,
        }


class Dummy(bt.Synapse):
    """
    Legacy dummy protocol - kept for backward compatibility with tests.
    Use ReviewSubmission for actual subnet operations.
    """

    dummy_input: int
    dummy_output: typing.Optional[int] = None

    def deserialize(self) -> int:
        return self.dummy_output
