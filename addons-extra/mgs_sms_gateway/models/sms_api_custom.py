import logging
from odoo.addons.sms.tools.sms_api import SmsApi  # type: ignore

_logger = logging.getLogger(__name__)


class SmsApiCustom(SmsApi):
    """Custom SmsApi class that routes messages to the Telesom gateway."""

    def _send_sms_batch(self, messages, delivery_reports_url=None):
        _logger.info("Routing SMS through custom Telesom Gateway")

        telesom_gateway = self.env["mgs_sms_gateway.telesom"]

        results = []
        for message in messages:
            content = message["content"]
            for num_data in message["numbers"]:
                phone = num_data["number"]
                uuid = num_data["uuid"]

                success, response_msg = telesom_gateway._send_sms_telesom(
                    phone, content
                )
                results.append(
                    {
                        "uuid": uuid,
                        "state": "success" if success else "server_error",
                        "failure_reason": None if success else response_msg,
                    }
                )

        _logger.info("Telesom results: %s", results)
        return results
