from __future__ import annotations

import logging

from sentry.tasks.base import instrumented_task
from sentry.taskworker.namespaces import integrations_tasks
from sentry.taskworker.retry import Retry

logger = logging.getLogger(__name__)


@instrumented_task(
    name="sentry.seer.entrypoints.slack.process_mention_for_slack",
    namespace=integrations_tasks,
    processing_deadline_duration=300,
    retry=Retry(times=2, delay=30),
)
def process_mention_for_slack(
    *,
    integration_id: int,
    organization_id: int,
    channel_id: str,
    thread_ts: str | None,
    message_ts: str,
    text: str,
    slack_user_id: str,
    bot_user_id: str,
) -> None:
    """
    Process a Slack @mention for Seer Explorer.

    Parses the mention, extracts thread context,
    and triggers an Explorer run via SeerOperator.
    """
    from sentry.models.organization import Organization
    from sentry.seer.entrypoints.metrics import (
        SlackEntrypointEventLifecycleMetric,
        SlackEntrypointInteractionType,
    )
    from sentry.seer.entrypoints.operator import SeerOperator
    from sentry.seer.entrypoints.slack.entrypoint import (
        SlackEntrypoint,
        SlackExplorerCompletionHook,
    )
    from sentry.seer.entrypoints.slack.mention import build_thread_context, extract_prompt

    with SlackEntrypointEventLifecycleMetric(
        interaction_type=SlackEntrypointInteractionType.PROCESS_MENTION,
        integration_id=integration_id,
        organization_id=organization_id,
    ).capture() as lifecycle:
        lifecycle.add_extras(
            {
                "channel_id": channel_id,
                "thread_ts": thread_ts,
                "message_ts": message_ts,
                "slack_user_id": slack_user_id,
            },
        )

        try:
            organization = Organization.objects.get_from_cache(id=organization_id)
        except Organization.DoesNotExist:
            lifecycle.record_halt(halt_reason="org_not_found")
            return

        if not SlackEntrypoint.has_explorer_access(organization):
            lifecycle.record_halt(halt_reason="no_explorer_access")
            return

        try:
            entrypoint = SlackEntrypoint.from_explorer_mention(
                integration_id=integration_id,
                organization_id=organization_id,
                channel_id=channel_id,
                message_ts=message_ts,
                thread_ts=thread_ts,
                slack_user_id=slack_user_id,
            )
        except ValueError:
            lifecycle.record_halt(halt_reason="integration_not_found")
            return

        # Immediately acknowledge the mention so the user knows we're processing
        entrypoint.install.add_reaction(
            channel_id=channel_id,
            message_ts=message_ts,
            emoji="thinking_face",
        )

        prompt = extract_prompt(text, bot_user_id)

        thread_context: str | None = None
        if thread_ts:
            messages = entrypoint.install.get_thread_history(
                channel_id=channel_id, thread_ts=thread_ts
            )
            thread_context = build_thread_context(messages) or None

        operator = SeerOperator(entrypoint=entrypoint)
        operator.trigger_explorer(
            organization=organization,
            user=None,
            prompt=prompt,
            on_page_context=thread_context,
            on_completion_hook=SlackExplorerCompletionHook,
            category_key="slack_thread",
            category_value=f"{channel_id}:{entrypoint.thread_ts}",
        )
