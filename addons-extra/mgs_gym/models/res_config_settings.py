from odoo import fields, models  # type: ignore


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    # Global System Parameters for SMS Provider
    sms_api_url = fields.Char(
        string="SMS API URL",
        config_parameter="mgs_gym.sms_api_url",
        help="The endpoint URL for your SMS provider (e.g., Twilio, Plivo, Telesom...).",
    )
    sms_password = fields.Char(
        string="Sender Password",
        config_parameter="mgs_gym.telesom_password",
    )
    sms_username = fields.Char(
        string="Sender Username",
        config_parameter="mgs_gym.telesom_username",
    )
    sms_api_secret = fields.Char(
        string="API Secret/Password",
        config_parameter="mgs_gym.sms_api_secret",
        help="The secret key or password (sensitive information).",
    )
    sms_sender_id = fields.Char(
        string="Sender ID/Number",
        config_parameter="mgs_gym.sms_sender_id",
        help="The registered sender ID or phone number.",
    )
