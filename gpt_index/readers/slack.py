"""Slack reader."""
import logging
import os
from typing import Any, List, Optional
import time
from tqdm import tqdm
import streamlit as st

from gpt_index.readers.base import BaseReader
from gpt_index.schema import Document

logger = logging.getLogger(__name__)


class SlackReader(BaseReader):
    """Slack reader.

    Reads conversations from channels.

    """

    def __init__(self, slack_token: Optional[str] = None) -> None:
        """Initialize with parameters."""
        try:
            from slack_sdk import WebClient
        except ImportError:
            raise ValueError(
                "`slack_sdk` package not found, please run `pip install slack_sdk`"
            )
        if slack_token is None:
            slack_token = os.environ["SLACK_BOT_TOKEN"]
            if slack_token is None:
                raise ValueError(
                    "Must specify `slack_token` or set environment "
                    "variable `SLACK_BOT_TOKEN`."
                )
        self.client = WebClient(token=slack_token)
        res = self.client.api_test()
        if not res["ok"]:
            raise ValueError(f"Error initializing Slack API: {res['error']}")

    def _read_message(self, channel_id: str, message_ts: str) -> str:
        from slack_sdk.errors import SlackApiError

        """Read a message."""

        messages_text = []
        next_cursor = None
        while True:
            # https://slack.com/api/conversations.replies
            # List all replies to a message, including the message itself.
            time.sleep(1)
            result = self.client.conversations_replies(
                channel=channel_id, ts=message_ts, cursor=next_cursor, limit=1000
            )
            try:
                messages = result["messages"]
                for message in messages:
                    messages_text.append(message["text"])

                if not result["has_more"]:
                    break

                next_cursor = result["response_metadata"]["next_cursor"]
            except SlackApiError as e:
                logger.error("Error parsing conversation replies: {}".format(e))
                break

        return "\n\n".join(messages_text)

    def _read_channel(self, channel_id: str) -> str:
        from slack_sdk.errors import SlackApiError

        """Read a channel."""

        result_messages = []
        next_cursor = None
        while True:
            time.sleep(1)
            result = self.client.conversations_history(
                channel=channel_id, cursor=next_cursor, limit=1000
            )
            try:
                # Call the conversations.history method using the WebClient
                # conversations.history returns the first 100 messages by default
                # These results are paginated,
                # see: https://api.slack.com/methods/conversations.history$pagination
                time.sleep(1)
                result = self.client.conversations_history(channel=channel_id, limit=1000)
                conversation_history = result["messages"]
                # Print results
                logger.info(
                    "{} messages found in {}".format(len(conversation_history), id)
                )
                for message in tqdm(conversation_history, "Reading messages"):
                    result_messages.append(
                        self._read_message(channel_id, message["ts"])
                    )

                # if not result["has_more"]:
                break
                next_cursor = result["response_metadata"]["next_cursor"]

            except SlackApiError as e:
                logger.error("Error creating conversation: {}".format(e))
                break

        return "\n\n".join(result_messages)

    @st.cache
    def load_data(self, **load_kwargs: Any) -> List[Document]:
        """Load data from the input directory."""
        channel_ids = load_kwargs.pop("channel_ids", None)
        if channel_ids is None:
            raise ValueError('Must specify a "channel_id" in `load_kwargs`.')

        results = []
        for channel_id in channel_ids:
            channel_content = self._read_channel(channel_id)
            results.append(
                Document(channel_content, extra_info={"channel": channel_id})
            )
        return results


if __name__ == "__main__":
    reader = SlackReader()
    print(reader.load_data(channel_ids=["C04DC2VUY3F"]))