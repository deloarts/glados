---
title: Project Lifecycle
summary: Which statuses a project moves through, what on hold, completed and archived mean for its work, and what keeps a project from being completed or deleted.
sourceRefs:
  - backend/src/modules/workspace/domain/services/lifecycle/project.py
  - backend/src/modules/workspace/domain/policies/project_activity.py
  - backend/src/modules/workspace/domain/value_objects/project_live_work.py
  - backend/src/modules/workspace/domain/services/project_rules.py
lastVerified: 2026-11-10
---

<script setup lang="ts">
import StateMachineEmbed from '@/features/handbook/state-machines/components/StateMachineEmbed.vue'
</script>

A project's status is set by hand under **Status** in its form. Nothing works it out from the project's lots or orders, but those decide which moves are allowed. This page shows the statuses and what each move does. How projects are created and edited is on [Projects](/handbook/workspace/projects).

<StateMachineEmbed machine-key="project_status" />

## What each status means

A new project starts **Active**, and only an active project takes new work: new demands, new lots, order lines moved onto it and lines reopened on it. **On Hold** stops new work while the open work goes on, so lots already running finish and ordered parts are still delivered. **Completed** and **Archived** close the project. Work already on a project that is not active can still be ordered, delivered, corrected and closed, so it can be cleaned up. Active projects appear on the **Current projects** widget of an infoscreen.

## Moving the status

An active project goes on hold, and a held one becomes active again. A project is completed from active or on hold, and archived from any of the three. A completed or archived project can be reopened, which makes it active again. Every move needs **Manage Projects**. The designated user may edit the rest of the project but not its status. In the form a status the project cannot move to now stays in the list, greyed out, with the reason underneath: the missing permission, the open work, or the current status it cannot leave that way.

## Open work

Completing, archiving and deleting a project need it to have no open work: no lot that is neither completed, canceled nor scrapped, no production order that is neither completed nor canceled, no order line that is neither delivered nor canceled, no open demand, and no open quote request with a line for the project. The reason under the status names the counts, such as 2 lots and 1 order line. Holding a project is allowed with open work.

## Examples

**A customer pauses the order.** You set the project **On Hold**. The lots already in production go on, but nobody can add a demand to it until you set it **Active** again.

**Closing a finished project.** One order line is still open, so **Completed** shows greyed out and names it. Once the line is delivered or canceled, you complete the project.

**A follow-up order.** The customer orders spare parts for a completed project. Setting it **Active** again reopens it for new demands.
