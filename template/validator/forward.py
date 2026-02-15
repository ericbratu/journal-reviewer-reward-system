import time
import bittensor as bt

from template.protocol import ReviewSubmission
from template.validator.llm_scorer import score_reviews_grouped
from template.utils.uids import get_random_uids


async def forward(self):
    miner_uids = get_random_uids(self, k=self.config.neuron.sample_size)
    bt.logging.info(f"Querying {len(miner_uids)} miners for reviews...")

    responses = await self.dendrite(
        axons=[self.metagraph.axons[uid] for uid in miner_uids],
        synapse=ReviewSubmission(),
        deserialize=False,
    )

    valid = sum(1 for r in responses if r.paper_id is not None)
    bt.logging.info(f"Received {valid}/{len(responses)} valid submissions")

    if valid == 0:
        bt.logging.warning("No valid reviews received, skipping")
        time.sleep(5)
        return

    try:
        rewards, scored_uids = await score_reviews_grouped(self, responses)
        bt.logging.info(f"Rewards - min: {rewards.min():.3f}, max: {rewards.max():.3f}, mean: {rewards.mean():.3f}")
        self.update_scores(rewards, scored_uids)
    except Exception as e:
        bt.logging.error(f"Scoring error: {e}")
        import traceback
        bt.logging.error(traceback.format_exc())

    time.sleep(5)
