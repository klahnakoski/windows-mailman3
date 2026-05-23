"""Entry point: POP3 → Mailman inline pipeline.

This is a thin wrapper around aws-email/remote/pop3_to_lmtp.py.
It reuses Pop3ToLmtp and Pop3 unchanged, replaces LazyLmtp with DirectLmtp
(no TCP socket — calls LMTPHandler._handle_DATA directly), and replaces
start_mailman() with setup_inline_pipeline().

Run::

    python pop3_to_lmtp.py [path/to/mailman.cfg]

config.json is expected in the current working directory (same as before).
"""

import sys
import boto3

from mo_dots import listwrap
from mo_json_config import get
from mo_logs import logger


# Reuse the original Pop3ToLmtp and Pop3 classes unchanged.
sys.path.insert(0, r'C:\Users\kyle\code\aws-email\remote')
from mailman.core.inline_pipeline import DirectLmtp, setup_inline_pipeline
from pop3 import Pop3  # noqa: E402
from pop3_to_lmtp import Pop3ToLmtp  # noqa: E402


def main():
    mailman_cfg = sys.argv[1] if len(sys.argv) > 1 else None
    boto3.setup_default_session(region_name="us-east-1")
    config = get("file://config.json")
    with logger.start(config.logs):
        # Replace start_mailman() + LazyLmtp with a single in-process call.
        setup_inline_pipeline(mailman_cfg or config.get('mailman_cfg'))
        with DirectLmtp() as lmtp:
            for username in listwrap(config.pop3.username):
                with Pop3(username=username, kwargs=config.pop3) as pop3:
                    Pop3ToLmtp(
                        pop3=pop3,
                        lmtp=lmtp,
                        aliases=config.aliases,
                        dmark_config=config.dmark,
                    ).move_mail()


if __name__ == '__main__':
    main()

