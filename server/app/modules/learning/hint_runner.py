from collections.abc import Callable
from contextlib import AbstractContextManager

from .hint_service import HintService
from .model_worker import ModelTransport, evaluate_candidate


async def run_one(
    transaction: Callable[[], AbstractContextManager[HintService]],
    transport: ModelTransport,
    content_check: Callable[[dict[str, str]], bool],
) -> bool:
    """Execute one committed permit in the independent hint worker's processing loop.

    A deployment supplies a verified transport and content gate explicitly. On worker loss
    after commit the next sweep holds unknown fees; the request is never dispatched again.
    """
    with transaction() as service:
        permit = service.dispatch()
    if permit is None:
        return False
    candidate = await evaluate_candidate(
        permit.context, permit.model, transport=transport, content_check=content_check
    )
    with transaction() as service:
        service.finish(permit.hint_id, permit.lease_epoch, candidate)
    return True
