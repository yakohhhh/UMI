# Architecture decision records

One file per decision that is expensive to reverse. Copy the format of an existing record, number it, and link it from the PR that implements it. A decision that changes gets a new record that supersedes the old one; old records are not rewritten.

| # | Decision | Status |
| --- | --- | --- |
| [0001](0001-repository-layout.md) | Monorepo, web app stays at the root, one Python workspace | Accepted |
| [0002](0002-one-session-format.md) | One binary session format from the Clip to the database | Accepted |
| [0003](0003-hardware-abstraction.md) | Hardware abstraction layer and simulated drivers | Accepted |
| [0004](0004-backend-stack.md) | FastAPI, SQLAlchemy, Postgres; no PostGIS yet | Accepted |
| [0005](0005-device-identity.md) | Device identity and signed flags | Accepted |
| [0006](0006-privacy-enforcement.md) | Privacy is enforced at the edge and checked at the server | Accepted |
