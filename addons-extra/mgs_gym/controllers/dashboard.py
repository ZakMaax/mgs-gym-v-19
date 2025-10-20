from odoo import http  # type: ignore
from odoo.http import request  # type: ignore
from datetime import datetime, timedelta


class GymDashboardController(http.Controller):
    @http.route(
        "/mgs_gym/dashboard/data",
        type="jsonrpc",
        auth="public",
        csrf=False,
        cors="*",
    )
    def get_dashboard_data(self):
        Membership = request.env["mgs_gym.membership"].sudo()

        # Basic counts
        active_count = Membership.search_count([("state", "=", "Active")])
        expired_count = Membership.search_count([("state", "=", "Expired")])
        suspended_count = Membership.search_count([("state", "=", "Suspended")])

        # About to expire: next_invoice_date within next 7 days (and not already expired)
        today = datetime.today().date()
        in_seven = today + timedelta(days=7)
        about_to_expire = Membership.search_count(
            [
                ("next_invoice_date", ">=", today),
                ("next_invoice_date", "<=", in_seven),
                ("state", "=", "Active"),
            ]
        )

        # Grouping charts
        # By branch
        branches = Membership.formatted_read_group(
            [], aggregates=["id:count"], groupby=["branch_id"]
        )
        branch_labels = [
            item.get("branch_id") and item.get("branch_id")[1] or "Unassigned"
            for item in branches
        ]
        branch_data = [item.get("id:count") for item in branches]

        # By gender
        genders = Membership.formatted_read_group(
            [], aggregates=["id:count"], groupby=["gender"]
        )
        gender_labels = [item.get("gender") or "Unknown" for item in genders]
        gender_data = [item.get("id:count") for item in genders]

        # By recurrence unit
        recs = Membership.formatted_read_group(
            [], aggregates=["id:count"], groupby=["recurrence_unit"]
        )
        rec_labels = [item.get("recurrence_unit") or "Unknown" for item in recs]
        rec_data = [item.get("id:count") for item in recs]

        # Memberships over time (created by month)
        timeline = Membership.formatted_read_group(
            [], aggregates=["id:count"], groupby=["create_date:month"]
        )
        line_labels = []
        line_data = []
        for item in timeline:
            raw = item.get("create_date:month") or item.get("create_date")
            # raw may be a date or string like '2025-10'
            if isinstance(raw, str):
                label = raw
            else:
                label = str(raw)
            line_labels.append(label)
            line_data.append(item.get("id:count"))

        # Money received per month (posted customer invoices)
        Invoice = request.env["account.move"].sudo()
        invoices_timeline = Invoice.formatted_read_group(
            [("move_type", "=", "out_invoice"), ("state", "=", "posted")],
            aggregates=["amount_total:sum"],
            groupby=["invoice_date:month"],
        )
        money_labels = []
        money_data = []
        for item in invoices_timeline:
            raw = item.get("invoice_date:month") or item.get("invoice_date")
            if isinstance(raw, str):
                mlabel = raw
            else:
                mlabel = str(raw)
            money_labels.append(mlabel)
            # sum field name is 'amount_total'
            money_data.append(float(item.get("amount_total:sum") or 0.0))

        data = {
            "active": active_count,
            "expired": expired_count,
            "suspended": suspended_count,
            "about_to_expire": about_to_expire,
            "by_branch": {"labels": branch_labels, "data": branch_data},
            "by_gender": {"labels": gender_labels, "data": gender_data},
            "by_recurrence": {"labels": rec_labels, "data": rec_data},
            "timeline": {"labels": line_labels, "data": line_data},
            "money_monthly": {"labels": money_labels, "data": money_data},
        }

        return data
