/** @odoo-module **/
import { Component, useState, onWillStart, onMounted } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { rpc } from "@web/core/network/rpc";

export class GymDashboard extends Component {
  static template = "mgs_gym.Dashboard";

  setup() {
    this.state = useState({ data: null });
    this.actionService = useService("action");

    onWillStart(async () => {
      this.state.data = await this._loadData();
    });

    onMounted(() => {
      if (this.state.data) {
        this._renderCharts();
      }
    });
  }

  async _loadData() {
    try {
      const result = await rpc("/mgs_gym/dashboard/data");
      return result;
    } catch (error) {
      console.error("Error loading gym dashboard data:", error);
    }
  }

  openActiveMembershipsView() {
    this.actionService.doAction({
      type: "ir.actions.act_window",
      name: "Active Memberships",
      res_model: "mgs_gym.membership",
      views: [
        [false, "list"],
        [false, "form"],
      ],
      target: "current",
      domain: [["state", "=", "Active"]],
    });
  }

  openExpiredMembershipsView() {
    this.actionService.doAction({
      type: "ir.actions.act_window",
      name: "Expired Memberships",
      res_model: "mgs_gym.membership",
      views: [
        [false, "list"],
        [false, "form"],
      ],
      target: "current",
      domain: [["state", "=", "Expired"]],
    });
  }

  openSuspendedMembershipsView() {
    this.actionService.doAction({
      type: "ir.actions.act_window",
      name: "Suspended Memberships",
      res_model: "mgs_gym.membership",
      views: [
        [false, "list"],
        [false, "form"],
      ],
      target: "current",
      domain: [["state", "=", "Suspended"]],
    });
  }

  openAboutToExpireView() {
    const today = new Date().toISOString().slice(0, 10);
    const inSeven = new Date();
    inSeven.setDate(inSeven.getDate() + 7);
    const inSevenStr = inSeven.toISOString().slice(0, 10);

    this.actionService.doAction({
      type: "ir.actions.act_window",
      name: "About to Expire",
      res_model: "mgs_gym.membership",
      views: [
        [false, "list"],
        [false, "form"],
      ],
      target: "current",
      domain: [
        ["next_invoice_date", ">=", today],
        ["next_invoice_date", "<=", inSevenStr],
        ["state", "=", "Active"],
      ],
    });
  }

  _renderCharts() {
    setTimeout(() => {
      this._renderPie("gymBranchPie", this.state.data.by_branch);
      this._renderPie("gymGenderPie", this.state.data.by_gender);
      this._renderPie("gymRecurrencePie", this.state.data.by_recurrence);
      this._renderLine("gymTimelineLine", this.state.data.timeline);
      this._renderRevenueLine("gymRevenueLine", this.state.data.money_monthly);
    }, 200);
  }

  _renderPie(elementId, payload) {
    const ctx = document.getElementById(elementId);
    if (!ctx) return;
    const labels = payload.labels.map((l) => (l || "").toString());
    new Chart(ctx, {
      type: "pie",
      data: {
        labels: labels,
        datasets: [
          {
            data: payload.data,
            backgroundColor: [
              "#0d6efd",
              "#198754",
              "#ffc107",
              "#dc3545",
              "#6f42c1",
            ],
          },
        ],
      },
      options: {
        responsive: true,
      },
    });
  }

  _renderLine(elementId, payload) {
    const ctx = document.getElementById(elementId);
    if (!ctx) return;
    const numericData =
      payload && payload.data ? payload.data.map((d) => Number(d) || 0) : [];
    new Chart(ctx, {
      type: "line",
      data: {
        labels: payload.labels,
        datasets: [
          {
            label: "New memberships",
            data: numericData,
            borderColor: "#0d6efd",
            backgroundColor: "rgba(13,110,253,0.08)",
            tension: 0.25,
            fill: true,
          },
        ],
      },
      options: {
        responsive: true,
        plugins: { legend: { display: false } },
        scales: {
          y: {
            ticks: {
              // round tick labels to integers
              callback: function (value) {
                // ensure numeric and round
                const v = Number(value);
                if (isNaN(v)) return value;
                return Math.round(v);
              },
            },
          },
        },
      },
    });
  }

  _renderRevenueLine(elementId, payload) {
    const ctx = document.getElementById(elementId);
    if (!ctx || !payload) return;
    const numericData = payload.data
      ? payload.data.map((d) => Number(d) || 0)
      : [];
    new Chart(ctx, {
      type: "line",
      data: {
        labels: payload.labels,
        datasets: [
          {
            label: "Revenue",
            data: numericData,
            borderColor: "#198754",
            backgroundColor: "rgba(25,135,84,0.08)",
            tension: 0.25,
            fill: true,
          },
        ],
      },
      options: {
        responsive: true,
        plugins: { legend: { display: false } },
        scales: {
          y: {
            ticks: {
              callback: function (value) {
                // format as currency
                const v = Number(value);
                const formatted = new Intl.NumberFormat(undefined, {
                  style: "currency",
                  currency: "USD",
                  maximumFractionDigits: 2,
                }).format(isNaN(v) ? value : v);
                return formatted;
              },
            },
          },
        },
      },
    });
  }
}

registry.category("actions").add("mgs_gym.Dashboard", GymDashboard);
