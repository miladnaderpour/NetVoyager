# Contributing

Keep API and CLI contracts explicit. Put reusable network logic in `packages/`; keep HTTP handlers, CLI formatting, and task orchestration in their respective apps. Never commit credentials, scan results, or production inventories. Prefer a small focused change with a meaningful test when behavior is introduced.
