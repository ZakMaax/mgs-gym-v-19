from odoo import models, api, fields  # type: ignore


class GymShift(models.Model):
    _name = "mgs_gym.shift"
    _description = "GYM Branch Shift"

    name = fields.Char(string="Name", required=True)
    branch_id = fields.Many2one(
        "mgs_gym.branch",
        string="Branch",
        required=True,
        default=lambda self: self.env.user.default_branch_id,
    )
    company_id = fields.Many2one(
        related="branch_id.company_id", string="Company", required=True, readonly=True
    )
    coach_id = fields.Many2many("res.users", string="Coach", required=True)
    active = fields.Boolean(default=True)
    start_time = fields.Float(
        string="Start Hour", required=True, help="e.g., 6.0 = 6 AM, 18.5 = 6:30 PM"
    )
    end_time = fields.Float(
        string="End Hour", required=True, help="e.g., 6.0 = 6 AM, 18.5 = 6:30 PM"
    )
    # Shifts are schedule slots and do not reference services directly anymore.
    capacity = fields.Integer(
        string="Capacity",
        default=0,
        help="How many members can this shift handle. 0 for unlimited.",
    )

    @api.model
    def create(self, vals):
        # Infer AM/PM if needed
        vals = self._infer_am_pm(vals)
        return super().create(vals)

    def write(self, vals):
        # Infer AM/PM on write too
        vals = self._infer_am_pm(vals)
        return super().write(vals)

    def _infer_am_pm(self, vals):
        """
        Simple inference:
        - If 0 < time <= 12 → assume AM
        - If time > 12 → assume PM (24h format)
        """
        for field in ["start_time", "end_time"]:
            if field in vals:
                t = vals[field]
                if t <= 12:
                    # assume AM → leave as is
                    vals[field] = t
                else:
                    # assume PM → leave as 24h (user already entered 13..23)
                    vals[field] = t
        return vals
