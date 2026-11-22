# Boligloggen – Home Assistant integration: agent handoff

Start here: **`boligloggen-ha-integration-brief.md`** is the spec. It is self-contained and takes precedence over everything in `docs/`.

## Contents

| File | Role |
|---|---|
| `boligloggen-ha-integration-brief.md` | The build brief: scope, architecture, data model, scheduling rules, entities, services, phases and acceptance criteria. |
| `docs/huslogg-onboarding.md` | Background (Norwegian): the onboarding question set and how each answer shapes the plan. Use it to write the config flow labels and the task catalog. |
| `docs/huslogg-applikasjonsplan.md` | Background (Norwegian): the product plan, roles and maintenance model. |

## Notes for the agent

- The product was earlier called "Huslogg"; it is now **Boligloggen**. The background docs still use the old name, so read "Huslogg" as "Boligloggen".
- The background docs describe a full app with a .NET Web API, push notifications, invitations and ownership transfer. **None of that applies here.** The integration is standalone and runs only inside Home Assistant. Where the brief and the docs disagree, follow the brief.
- Begin with phase 1 in the brief (§12): the pure Python planner, catalog and tests, with no Home Assistant dependency.
