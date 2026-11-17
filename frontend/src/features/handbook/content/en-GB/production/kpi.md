---
title: KPIs
summary: Which production figures the KPIs tab shows, how the period and scope filters narrow them and how to read a tile, a chart and the late lots table.
sourceRefs:
  - frontend/src/features/production/kpi/views/ProductionKpiView.vue
  - frontend/src/features/production/kpi/components/KpiFiltersBar.vue
  - frontend/src/features/production/kpi/utils/periodPresets.ts
  - backend/src/modules/quality/application/use_cases/production_kpi/compute_production_kpis.py
  - backend/src/modules/quality/domain/services/kpi_rules.py
lastVerified: 2026-11-10
---

The **KPIs** tab under Production measures how well production kept its dates, used its machines and made good parts. Every figure is worked out from the orders, completions and deliveries already recorded, so nothing needs to be entered here, and the tiles follow the ISO 22400 definitions.

## Choosing the period and scope {#filters}

**Period** picks **This Week**, **Last Week**, **This Month**, **Last Month**, **Last 90 Days** or a **Custom Range**, and the tab opens on This Month. **Machine / Pool** narrows the figures to one machine or one pool, and **Project** and **Customer** narrow them to one project or customer. **Clear** goes back to This Month with no scope, and **Sync** loads the figures again.

## Reading a tile {#tiles}

The tiles across the top are **Schedule Adherence**, **On-Time Delivery**, **Throughput Time**, **Utilization**, **First Pass Yield**, **Scrap Ratio** and **Rework Ratio**. **Availability** and **OEE** join them once there is enough data to compute them. Hover the information icon on a tile for its exact definition. The small line under the value says how many orders, lots or pieces it is based on.

The change next to the value compares it to the previous period of the same length. It shows green when the figure got better and red when it got worse, so a rising scrap ratio is red. A tile that shows **n/a** has nothing to measure in the period, and the line under it says why.

## Charts and tables {#panels}

The weekly chart puts schedule adherence and on-time delivery side by side per calendar week, and the machine chart shows utilization and availability per machine. **Estimate Accuracy by Fabrication Method** compares the real work time with the estimate, where a ratio above 100% means the work took longer. **Waiting Time Between Steps** shows how long an order waits after the step before it is ready. **Quality by Item**, **Scrap by Reason** and **Rejected at Receipt by Supplier** show where parts were lost.

**Late & At-Risk Lots** lists the open lots whose planned end is past their target date, most days late first, with the **Driver** that holds them back. It ignores the period, because it shows the plan as it stands today.

## Examples {#examples}

A planner opens the tab on the first working day of a month. This Month has little data yet, so they switch to **Last Month** to review the month that just ended.

Schedule Adherence shows 72% with a red arrow. Setting **Machine / Pool** to one machine at a time shows which machine finished its orders late.

A lot appears under Late & At-Risk Lots with the driver **Missing material**. The material has not arrived, and the lot will stay late until it does.
