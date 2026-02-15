import time
import typing
import bittensor as bt

import template
from template.base.miner import BaseMinerNeuron


class Miner(BaseMinerNeuron):

    def __init__(self, config=None):
        super(Miner, self).__init__(config=config)

        from template.data.review_dataset import ReviewDataset

        data_path = getattr(self.config, 'data_path', 'data/processed')
        miner_id = getattr(self.config, 'miner_id', 0)
        self.review_dataset = ReviewDataset(data_path=data_path, miner_id=miner_id)

    async def forward(
        self, synapse: template.protocol.ReviewSubmission
    ) -> template.protocol.ReviewSubmission:
        review = self.review_dataset.get_next()
        if review is None:
            bt.logging.warning("No reviews available")
            return synapse

        synapse.paper_id = review["paper_id"]
        synapse.review_text = review.get("review_text", "")
        synapse.review_metadata = {
            "title": review.get("title", ""),
            "rating": review.get("rating", ""),
        }
        bt.logging.info(f"Submitted review for paper {synapse.paper_id[:12]}...")
        return synapse

    async def blacklist(
        self, synapse: template.protocol.ReviewSubmission
    ) -> typing.Tuple[bool, str]:
        if synapse.dendrite is None or synapse.dendrite.hotkey is None:
            bt.logging.warning("Received a request without a dendrite or hotkey.")
            return True, "Missing dendrite or hotkey"

        uid = self.metagraph.hotkeys.index(synapse.dendrite.hotkey)
        if (
            not self.config.blacklist.allow_non_registered
            and synapse.dendrite.hotkey not in self.metagraph.hotkeys
        ):
            bt.logging.trace(f"Blacklisting un-registered hotkey {synapse.dendrite.hotkey}")
            return True, "Unrecognized hotkey"

        if self.config.blacklist.force_validator_permit:
            if not self.metagraph.validator_permit[uid]:
                bt.logging.warning(f"Blacklisting non-validator hotkey {synapse.dendrite.hotkey}")
                return True, "Non-validator hotkey"

        bt.logging.trace(f"Not blacklisting recognized hotkey {synapse.dendrite.hotkey}")
        return False, "Hotkey recognized!"

    async def priority(self, synapse: template.protocol.ReviewSubmission) -> float:
        if synapse.dendrite is None or synapse.dendrite.hotkey is None:
            bt.logging.warning("Received a request without a dendrite or hotkey.")
            return 0.0

        caller_uid = self.metagraph.hotkeys.index(synapse.dendrite.hotkey)
        priority = float(self.metagraph.S[caller_uid])
        bt.logging.trace(f"Prioritizing {synapse.dendrite.hotkey} with value: {priority}")
        return priority


if __name__ == "__main__":
    with Miner() as miner:
        while True:
            bt.logging.info(f"Miner running... {time.time()}")
            time.sleep(5)
