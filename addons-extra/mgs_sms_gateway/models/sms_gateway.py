import hashlib
import requests
import urllib.parse
import re
import json
from datetime import date, datetime
from odoo import models, api, _  # type: ignore
import logging

_logger = logging.getLogger(__name__)


class TelesomSMSGateway(models.AbstractModel):
    _name = "mgs_sms_gateway.telesom"
    _description = "Telesom SMS Gateway Implementation"

    def _get_telesom_credentials(self):
        """Retrieve Telesom credentials from system parameters."""
        get_param = self.env["ir.config_parameter"].sudo().get_param
        return {
            "username": get_param("mgs_gym.telesom_username"),
            "password": get_param("mgs_gym.telesom_password"),
            "sender": get_param("mgs_gym.sms_sender_id"),
            "private_key": get_param("mgs_gym.sms_api_secret"),
            "api_url": get_param("mgs_gym.sms_api_url"),
        }

    def _send_sms_telesom(self, mobile, message):
        """
        Send a single SMS via Telesom API.
        Returns: tuple(success: bool, response: str)
        """
        creds = self._get_telesom_credentials()

        # 1️⃣ Validation
        if not all(
            [
                creds["username"],
                creds["password"],
                creds["sender"],
                creds["private_key"],
                creds["api_url"],
            ]
        ):
            _logger.error("Telesom credentials are incomplete in system settings.")
            return False, "Telesom configuration incomplete"

        if not mobile:
            return False, "Missing mobile number"

        # 2️⃣ Prepare data
        current_date = datetime.strptime(str(date.today()), "%Y-%m-%d").strftime(
            "%d/%m/%Y"
        )
        cleaned_message = re.sub(r'[/@$%^&*()={}|\<>~`"#]', ":", message)
        encoded_message = urllib.parse.quote(cleaned_message)
        cleaned_mobile = mobile.replace(" ", "").replace("+", "")

        # 3️⃣ Generate hashkey
        hash_input = "|".join(
            [
                creds["username"],
                creds["password"],
                cleaned_mobile,
                encoded_message,
                creds["sender"],
                current_date,
                creds["private_key"],
            ]
        )
        hashkey = hashlib.md5(hash_input.encode("utf-8")).hexdigest().upper()

        # 4️⃣ Construct API URL
        url = f"{creds['api_url'].rstrip('/')}/{creds['sender']}/{encoded_message}/{cleaned_mobile}/{hashkey}"
        _logger.info("Telesom sending SMS to %s using URL: %s", cleaned_mobile, url)

        # 5️⃣ Send request
        try:
            response = requests.get(url, timeout=10)
            response_text = response.text

            # Try parsing JSON response if provider returns JSON
            try:
                response_json = json.loads(response_text)
                status = response_json.get("status")
                if status == "error":
                    _logger.warning("Telesom SMS failed: %s", response_text)
                    return False, response_text
                else:
                    return True, response_text
            except json.JSONDecodeError:
                # Fallback: check for common success keywords in plain text
                if any(
                    x in response_text.lower() for x in ["success", "accepted", "0"]
                ):
                    return True, response_text
                else:
                    _logger.warning("Telesom SMS failed (non-JSON): %s", response_text)
                    return False, response_text

        except requests.RequestException as e:
            _logger.error("Network error sending SMS via Telesom: %s", str(e))
            return False, f"Network Error: {str(e)}"
