from odoo import models, fields  # type: ignore


class PropertyStage(models.Model):
    _name = "mgs_gym.membership_state"
    _description = "GYM Membership State"
    _order = "sequence, name, id"
    _rec_name = "name"

    name = fields.Char(string="State", required=True, translate=True)
    sequence = fields.Integer(string="Sequence", default=1)
