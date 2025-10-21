from odoo import models, fields, api  # type: ignore
from odoo.exceptions import UserError  # type: ignore
from datetime import timedelta
import logging

_logger = logging.getLogger(__name__)


class GymMembership(models.Model):
    _name = "mgs_gym.membership"
    _description = "Gym Membership"
    _inherit = ["mail.activity.mixin", "mail.tracking.duration.mixin"]

    _track_duration_field = "state_id"

    name = fields.Char(string="Name", default="/", required=True, readonly=True)
    partner_id = fields.Many2one(
        "res.partner",
        required=True,
        string="Client",
        domain=[("is_gym_member", "=", True)],
    )
    branch_id = fields.Many2one(
        related="partner_id.branch_id", string="Branch", store=True, readonly=True
    )
    active = fields.Boolean(default=True)
    gender = fields.Selection(related="partner_id.gender", store=True, readonly=True)

    shift_id = fields.Many2one(
        "mgs_gym.shift",
        string="Shift",
        required=True,
        tracking=True,
        domain="[('branch_id', '=', branch_id)]",
    )
    class_id = fields.Many2one(
        "mgs_gym.class",
        string="Class",
        tracking=True,
        domain="[('shift_id', '=', shift_id)]",
    )

    recurrence_unit = fields.Selection(
        [
            ("daily", "Daily"),
            ("weekly", "Weekly"),
            ("monthly", "Monthly"),
            ("quarterly", "Quarterly"),
            ("yearly", "Yearly"),
        ],
        string="Recurrence Unit",
        default="monthly",
        required=True,
    )

    recurrence_interval = fields.Integer(
        string="Recurrence Interval",
        default=1,
        help="Every X recurrence unit(s)",
    )

    service_id = fields.Many2one(
        "product.template",
        domain="[('type', '=', 'service')]",
        string="Base Service Product",
        required=True,
    )

    recurrence_product_id = fields.Many2one(
        "product.product",
        string="Membership Service (Variant)",
        readonly=True,
        help="Selected automatically based on the recurrence unit and base service.",
    )

    amount = fields.Monetary(
        string="Amount",
        currency_field="company_currency_id",
        tracking=True,
        readonly=True,
    )

    discount_percent = fields.Float(
        string="Discount (%)",
        default=0.0,
        help="Percentage discount to apply to activation or renewal invoices.",
    )

    discount_amount = fields.Monetary(
        string="Discount Amount",
        currency_field="company_currency_id",
        store=True,
        readonly=True,
        compute="_compute_discount_amount",
        help="Monetary value of the discount (computed from percent).",
    )

    discounted_amount = fields.Monetary(
        string="Discounted Amount",
        currency_field="company_currency_id",
        store=True,
        readonly=True,
        compute="_compute_discounted_price",
        help="Monetary value of the discount.",
    )

    start_date = fields.Date(
        string="Start Date",
        required=True,
        default=fields.Date.today,
    )

    next_invoice_date = fields.Date(
        string="Date of Expiry",
        help="The next scheduled invoice generation date (expiration date).",
    )

    company_id = fields.Many2one(
        "res.company", default=lambda self: self.env.company, readonly=True
    )

    company_currency_id = fields.Many2one(
        related="company_id.currency_id",
        readonly=True,
    )

    state_id = fields.Many2one(
        "mgs_gym.membership_state",
        string="State ID",
        index=True,
        store=True,
        default=lambda self: self._default_state_id(),
        group_expand="_read_group_state_ids",
        tracking=True,
        copy=False,
        ondelete="restrict",
    )
    state = fields.Char(
        related="state_id.name", string="State", store=True, translate=True
    )

    can_renew = fields.Boolean(
        string="Can Renew",
        compute="_compute_can_renew",
        store=True,
        help="True when membership is in Expired state and can be renewed.",
    )

    invoice_journal_id = fields.Many2one(
        "account.journal",
        string="Invoice Journal",
        domain=[("type", "=", "sale")],
        help="Journal used to create customer invoices and credit notes.",
        required=True,
    )

    payment_journal_id = fields.Many2one(
        "account.journal",
        string="Payment Journal",
        domain=[("type", "in", ["bank", "cash"])],
        help="Journal used to post payments (bank/cash).",
        required=True,
    )
    refund_due = fields.Monetary(
        string="Refund Due",
        compute="_compute_refund_due",
        currency_field="company_currency_id",
        help="Prorated amount to return to the member if suspended today.",
        store=True,
    )
    refunded = fields.Boolean(string="Refunded", default=False, readonly=True)
    _first_invoice_done = fields.Boolean(default=False, readonly=True)

    # -------------------------------
    # Default and state methods
    # -------------------------------
    @api.model
    def _read_group_state_ids(self, states, domain):
        return self.env["mgs_gym.membership_state"].search([], order="sequence, id")

    def _default_state_id(self):
        return self.env["mgs_gym.membership_state"].search(
            [], limit=1, order="sequence"
        )

    @api.depends("state")
    def _compute_can_renew(self):
        expired = self.env["mgs_gym.membership_state"].search(
            [("name", "=", "Expired")], limit=1
        )
        for rec in self:
            rec.can_renew = bool(expired and rec.state_id == expired)

    @api.depends("amount", "discount_percent")
    def _compute_discount_amount(self):
        for record in self:
            percent = float(record.discount_percent or 0.0)
            record.discount_amount = round(
                (record.amount or 0.0) * (percent / 100.0), 2
            )

    @api.depends("amount", "discount_percent", "discount_amount")
    def _compute_discounted_price(self):
        for record in self:
            record.discounted_amount = record.amount - record.discount_amount

    def _effective_price(self):
        """Return price after applying discount_amount (never negative)."""
        self.ensure_one()
        return max(0.0, float((self.amount or 0.0) - (self.discount_amount or 0.0)))

    # -------------------------------
    # Onchange methods
    # -------------------------------
    @api.onchange("partner_id")
    def _onchange_partner_id(self):
        for record in self:
            record.branch_id = (
                record.partner_id.branch_id.id if record.partner_id.branch_id else False
            )

    @api.onchange("recurrence_unit", "recurrence_interval", "service_id")
    def _onchange_service_or_unit(self):
        """Compute recurrence product and amount whenever service or unit changes."""
        self._compute_recurrence_product_and_amount()

    # -------------------------------
    # Helper method for recurrence
    # -------------------------------
    def _compute_recurrence_product_and_amount(self):
        """
        Computes the Recurrence Product (variant) and the base Amount.
        - Looks for a product variant matching the recurrence unit name in the selected service.
        """
        variant_map = {
            "weekly": "Weekly",
            "daily": "Daily",
            "monthly": "Monthly",
            "quarterly": "Quarterly",
            "yearly": "Yearly",
        }

        for record in self:
            if not record.service_id:
                record.recurrence_product_id = False
                record.amount = 0
                continue

            base_service = record.service_id
            base_price = base_service.list_price or 0
            variant_name = variant_map.get(record.recurrence_unit)

            # Search for the product variant matching the recurrence unit attribute
            variant = base_service.product_variant_ids.filtered(
                lambda p: any(
                    v.name == variant_name
                    for v in p.product_template_attribute_value_ids
                )
            )

            if variant:
                record.recurrence_product_id = variant[0].id
                unit_price = variant[0].lst_price
            else:
                # Fallback: Use the base service product's default variant and price
                record.recurrence_product_id = base_service.product_variant_id.id
                unit_price = base_price

            interval = record.recurrence_interval or 1
            raw_amount = unit_price * interval

            # Store raw amount
            record.amount = float(round(raw_amount, 2))

    # -------------------------------
    # Billing logic (no changes)
    # -------------------------------
    @api.onchange("recurrence_unit", "recurrence_interval", "start_date")
    def _onchange_billing(self):
        for record in self:
            if not record.start_date:
                continue

            unit = record.recurrence_unit
            interval = record.recurrence_interval or 1
            next_date = record.start_date

            if unit == "daily":
                next_date += timedelta(days=interval)
            elif unit == "weekly":
                next_date += timedelta(weeks=interval)
            elif unit == "monthly":
                next_date = fields.Date.add(next_date, months=interval)
            elif unit == "quarterly":
                next_date = fields.Date.add(next_date, months=3 * interval)
            elif unit == "yearly":
                next_date = fields.Date.add(next_date, years=interval)

            record.next_invoice_date = next_date

    def change_state(self, new_state_name):
        new_state = self.env["mgs_gym.membership_state"].search(
            [("name", "=", new_state_name)], limit=1
        )

        if not new_state:
            raise UserError(f"Stage '{new_state_name}' not found.")

        for membership in self:
            membership.state_id = new_state.id

    def make_cancelled(self):
        self.change_state("Cancelled")

    def make_suspended(self):
        self.change_state("Suspended")

    def make_draft(self):
        self.change_state("Draft")

    def make_active(self):
        """Activate or reactivate membership, generating invoice if refunded or missing."""
        self.change_state("Active")

        for membership in self:
            # Reset refund flag (if reactivated)
            was_refunded = membership.refunded
            membership.refunded = False

            # Check if there’s an existing posted invoice for this member and product
            has_invoice = self.env["account.move"].search_count(
                [
                    ("partner_id", "=", membership.partner_id.id),
                    ("move_type", "=", "out_invoice"),
                    ("state", "=", "posted"),
                    (
                        "invoice_line_ids.product_id",
                        "in",
                        [
                            membership.recurrence_product_id.id
                            or membership.service_id.id
                        ],
                    ),
                ]
            )

            # If refunded before, or if no invoice exists, generate a new one
            if was_refunded or not has_invoice:
                membership._generate_invoice()
                membership._first_invoice_done = True
                membership._onchange_billing()
                membership.message_post(
                    body=f"Membership {membership.name} {'reactivated' if was_refunded else 'activated'} and new invoice generated."
                )
            else:
                membership.message_post(
                    body=f"Membership {membership.name} activated without new invoice (existing invoice found)."
                )

    @api.depends(
        "state", "next_invoice_date", "recurrence_unit", "recurrence_interval", "amount"
    )
    def _compute_refund_due(self):
        """Compute prorated refund for suspended memberships."""
        today = fields.Date.today()
        today_dt = fields.Date.from_string(today)
        for rec in self:
            rec.refund_due = 0.0
            if rec.state != "Suspended" or not rec.next_invoice_date or not rec.amount:
                continue

            try:
                next_dt = fields.Date.from_string(rec.next_invoice_date)
            except Exception:
                continue

            if next_dt <= today_dt:
                # nothing left to refund
                continue

            interval = rec.recurrence_interval or 1

            # Determine period start date (the date when the current paid period began)
            if rec.recurrence_unit == "weekly":
                period_start_dt = next_dt - timedelta(weeks=interval)
            elif rec.recurrence_unit == "monthly":
                period_start_str = fields.Date.add(
                    rec.next_invoice_date, months=-interval
                )
                period_start_dt = fields.Date.from_string(period_start_str)
            elif rec.recurrence_unit == "quarterly":
                period_start_str = fields.Date.add(
                    rec.next_invoice_date, months=-(3 * interval)
                )
                period_start_dt = fields.Date.from_string(period_start_str)
            elif rec.recurrence_unit == "yearly":
                period_start_str = fields.Date.add(
                    rec.next_invoice_date, years=-interval
                )
                period_start_dt = fields.Date.from_string(period_start_str)
            else:
                # fallback: no refund
                continue

            days_in_period = (next_dt - period_start_dt).days or 1
            days_left = (next_dt - today_dt).days
            if days_left <= 0:
                continue

            refund = (rec._effective_price()) * (days_left / days_in_period)
            # round to currency precision (2 decimals)
            rec.refund_due = float(round(refund, 2))

    def action_refund(self):
        """Create a customer credit note for suspended memberships and register payment."""
        is_administrator = self.env.user.has_group("base.group_system")

        if not is_administrator:
            raise UserError("Only an administrator can process member refunds")
        Move = self.env["account.move"]
        for rec in self:
            if rec.state != "Suspended":
                raise UserError(
                    "Refunds can only be processed for Suspended memberships."
                )
            if rec.refunded:
                raise UserError("Refund already processed for this membership.")

            refund_amount = rec.refund_due
            if refund_amount <= 0:
                raise UserError("No refundable amount available.")

            if not rec.payment_journal_id:
                raise UserError("Please select a Payment Journal for refunds.")

            # Determine product used in refund line
            product = rec.recurrence_product_id or rec.service_id
            if not product:
                raise UserError("No product linked to this membership for refund line.")

            # --- 1️⃣ Create Credit Note ---
            refund_vals = {
                "partner_id": rec.partner_id.id,
                "move_type": "out_refund",
                "invoice_date": fields.Date.today(),
                "journal_id": rec.invoice_journal_id.id,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": product.id,
                            "name": f"Refund for Membership {rec.name}",
                            "price_unit": refund_amount,
                            "analytic_distribution": {
                                str(rec.branch_id.analytic_account_id.id): 100.0
                            }
                            if rec.branch_id.analytic_account_id
                            else {},
                        },
                    )
                ],
            }

            refund_move = Move.create(refund_vals)
            refund_move.action_post()

            # --- 2️⃣ Register payment on the Credit Note ---
            payment_register = (
                self.env["account.payment.register"]
                .with_context(active_model="account.move", active_ids=refund_move.ids)
                .create(
                    {
                        "payment_date": fields.Date.today(),
                        "journal_id": rec.payment_journal_id.id,
                        "payment_type": "outbound",
                    }
                )
            )
            payment_register.action_create_payments()

            # --- 3️⃣ Mark refunded and log message ---
            rec.refunded = True
            rec.message_post(
                body=f"Refund processed via Credit Note {refund_move.name} "
                f"for amount {refund_amount}."
            )

    # -------------------------------
    # Create override (Capacity Check Restored)
    # -------------------------------
    @api.model
    def create(self, vals_list):
        for vals in vals_list:
            # SHIFT CAPACITY CHECK: Check capacity based on the selected shift
            shift_id = vals.get("shift_id")
            if shift_id:
                shift = self.env["mgs_gym.shift"].browse(shift_id)
                if shift.capacity and shift.capacity > 0:
                    # Count active memberships in this shift
                    current_count = self.search_count(
                        [("shift_id", "=", shift.id), ("active", "=", True)]
                    )
                    if current_count >= shift.capacity:
                        raise UserError(
                            f"Shift '{shift.name}' is full ({shift.capacity} members)."
                        )

            if vals.get("name", "/") == "/":
                vals["name"] = (
                    self.env["ir.sequence"].next_by_code("mgs_gym.membership") or "/"
                )
        recs = super().create(vals_list)
        for membership in recs:
            # Recalculate product and amount (now based on user-entered service_id)
            membership._compute_recurrence_product_and_amount()
            # Calculate next invoice date after first invoice
            membership._onchange_billing()

        return recs

    @api.model
    def notify_upcoming_expirations(self):
        """Create reminder activities for memberships nearing expiration."""
        today = fields.Date.today()
        activity_type = self.env["mail.activity.type"].search(
            [("name", "=", "Membership Expiration Reminder")], limit=1
        )
        if not activity_type:
            activity_type = self.env["mail.activity.type"].create(
                {"name": "Membership Expiration Reminder"}
            )

        memberships = self.search(
            [
                ("next_invoice_date", "!=", False),
                ("state", "=", "Active"),
                ("active", "=", True),
                ("recurrence_unit", "!=", "daily"),
            ]
        )
        model = self.env["ir.model"]._get("mgs_gym.membership")
        for member in memberships:
            try:
                # Branch-based reminder days (default to 3)
                reminder_days = member.branch_id.reminder_days or 3
                # Skip if not yet within reminder window
                if member.next_invoice_date > today + timedelta(days=reminder_days):
                    continue

                # avoid creating duplicate reminders for same membership + activity type
                existing = self.env["mail.activity"].search(
                    [
                        ("res_model_id", "=", model.id),
                        ("res_id", "=", member.id),
                        ("activity_type_id", "=", activity_type.id),
                    ],
                    limit=1,
                )
                if existing.filtered(lambda a: a.state != "done"):
                    continue

                user = (
                    member.branch_id.manager_id
                    or self.env.ref("base.user_admin", raise_if_not_found=False)
                    or self.env.user
                )
                vals = {
                    "res_model_id": model.id,
                    "res_id": member.id,  # REQUIRED when res_model set
                    "activity_type_id": activity_type.id,
                    "summary": f"Membership for {member.partner_id.name} will expire soon",
                    "note": (
                        f"The membership for {member.partner_id.name} is set to expire on "
                        f"{member.next_invoice_date}. Please remind the member to renew."
                    ),
                    "user_id": user.id,
                    "date_deadline": member.next_invoice_date
                    or (today + timedelta(days=1)),
                }
                self.env["mail.activity"].create(vals)
            except Exception:
                _logger.exception(
                    "Failed to create expiration reminder for membership %s", member.id
                )

    #
    # SHOW PARTNER INVOICES
    #

    def action_view_invoices(self):
        self.ensure_one()
        return {
            "name": "Invoices",
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "view_mode": "list,form",
            "domain": [("partner_id", "=", self.partner_id.id)],
            "context": {"default_partner_id": self.partner_id.id},
        }

    def action_view_payments(self):
        self.ensure_one()
        return {
            "name": "Invoices",
            "type": "ir.actions.act_window",
            "res_model": "account.payment",
            "view_mode": "list,form",
            "domain": [("partner_id", "=", self.partner_id.id)],
            "context": {"default_partner_id": self.partner_id.id},
        }

    @api.model
    def expire_due_memberships(self):
        """Cron helper: mark memberships as Expired when their next_invoice_date is reached."""
        today = fields.Date.today()
        expired_state = self.env["mgs_gym.membership_state"].search(
            [("name", "=", "Expired")], limit=1
        )
        if not expired_state:
            return

        due_members = self.search(
            [
                ("next_invoice_date", "<=", today),
                ("state_id", "!=", expired_state.id),
                ("active", "=", True),
            ]
        )
        if due_members:
            due_members.write({"state_id": expired_state.id})

    def action_renew(self):
        """Renew an expired membership."""
        today = fields.Date.today()
        active_state = self.env["mgs_gym.membership_state"].search(
            [("name", "=", "Active")], limit=1
        )

        for membership in self:
            # Activate
            if active_state:
                membership.state_id = active_state.id

            # Create and post invoice for this renewal
            product = membership.recurrence_product_id or membership.service_id
            if not product:
                # Skip invoicing if there's no product configured
                continue

            invoice_vals = {
                "partner_id": membership.partner_id.id,
                "move_type": "out_invoice",
                "invoice_date": today,
                "journal_id": membership.invoice_journal_id.id,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": product.id,
                            "quantity": 1,
                            "price_unit": membership._effective_price(),
                            "analytic_distribution": {
                                str(membership.branch_id.analytic_account_id.id): 100.0
                            }
                            if membership.branch_id.analytic_account_id
                            else {},
                        },
                    )
                ],
            }

            invoice = self.env["account.move"].create(invoice_vals)
            invoice.action_post()
            membership._register_payment(invoice)
            # Recalculate next invoice date after successful renewal
            self._update_next_invoice_date(membership)
            # Mark old reminders as done
        model = self.env["ir.model"]._get("mgs_gym.membership")
        for membership in self:
            old_reminders = self.env["mail.activity"].search(
                [
                    ("res_model_id", "=", model.id),
                    ("res_id", "=", membership.id),
                    ("activity_type_id.name", "=", "Membership Expiration Reminder"),
                ]
            )
            old_reminders.filtered(lambda a: a.state == "planned").write(
                {"state": "done"}
            )
            old_reminders.write({"state": "done"})
            membership.write({"refunded": False})

    def _update_next_invoice_date(self, membership):
        """Update next_invoice_date starting from the latest of today or old next_invoice_date."""
        today = fields.Date.today()
        if not membership.start_date:
            return

        unit = membership.recurrence_unit
        interval = membership.recurrence_interval or 1

        # Use max(today, current next_invoice_date) as base
        base_date = max(today, membership.next_invoice_date or today)

        if unit == "daily":
            next_date = base_date + timedelta(days=interval)
        elif unit == "weekly":
            next_date = base_date + timedelta(weeks=interval)
        elif unit == "monthly":
            next_date = fields.Date.add(base_date, months=interval)
        elif unit == "quarterly":
            next_date = fields.Date.add(base_date, months=3 * interval)
        elif unit == "yearly":
            next_date = fields.Date.add(base_date, years=interval)
        else:
            next_date = base_date

        membership.write({"next_invoice_date": next_date})

    def _register_payment(self, invoice):
        """Automatically pay the invoice in the selected journal."""
        if not self.payment_journal_id:
            raise UserError("Please select a Payment Journal for automatic payment.")

        payment_method = self.env.ref(
            "account.account_payment_method_manual_in", raise_if_not_found=False
        ) or self.env.ref("account.account_payment_method_manual_out")

        payment_vals = {
            "payment_type": "inbound",
            "partner_type": "customer",
            "partner_id": invoice.partner_id.id,
            "amount": invoice.amount_total,
            "journal_id": self.payment_journal_id.id,
            "payment_method_id": payment_method.id if payment_method else False,
            "date": fields.Date.today(),
            "memo": invoice.name,
        }
        payment = self.env["account.payment"].create(payment_vals)
        payment.action_post()

    def _generate_invoice(self):
        """Generate invoice upon membership activation."""
        product = self.recurrence_product_id or self.service_id
        if not product:
            return

        price_unit = self._effective_price()

        invoice_vals = {
            "partner_id": self.partner_id.id,
            "move_type": "out_invoice",
            "invoice_date": fields.Date.today(),
            "journal_id": self.invoice_journal_id.id,
            "invoice_line_ids": [
                (
                    0,
                    0,
                    {
                        "product_id": product.id,
                        "quantity": 1,
                        "price_unit": price_unit,
                        "analytic_distribution": {
                            str(self.branch_id.analytic_account_id.id): 100.0
                        }
                        if self.branch_id.analytic_account_id
                        else {},
                    },
                )
            ],
        }

        invoice = self.env["account.move"].create(invoice_vals)
        invoice.action_post()
        self._register_payment(invoice)
        # Update next_invoice_date AFTER this first invoice
        self._update_next_invoice_date(self)

    @api.ondelete(at_uninstall=False)
    def _unlink_except_active_membership(self):
        for rec in self:
            if rec.state == "Active":
                raise UserError(
                    "You cannot delete an active membership. You need to Cancel it or Reset it to Draft first. Or Archive it instead"
                )

    def action_print_receipt(self):
        self.ensure_one()
        return self.env.ref(
            "mgs_gym.action_report_gym_membership_receipt"
        ).report_action(self)
