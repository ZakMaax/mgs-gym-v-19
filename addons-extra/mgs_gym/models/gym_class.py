from odoo import models, fields  # type: ignore


class GymShift(models.Model):
    _name = "mgs_gym.class"
    _description = "GYM Class"

    name = fields.Char("name")
    active = fields.Boolean(default=True)
    shift_id = fields.Many2one(
        "mgs_gym.shift",
        string="Shift",
        domain=lambda self: [("branch_id", "in", self.env.user.branch_ids.ids)],
    )
    coach_id = fields.Many2one("res.users", string="Coach", required=True)
    description = fields.Html(string="Description")
