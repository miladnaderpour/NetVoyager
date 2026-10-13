# 0007 - Design discovery for repeatable comparison

## Status

Accepted

## Context

A network discovery run should distinguish network changes from newly acquired knowledge and must detect interface movement even when canonical prefixes are unchanged.

## Decision

- Repeatable discovery compares object states **and** relevant source/association relationships, not only the set of `NetworkPrefix` CIDRs.
- Example: a route to the same destination moving from `ethernet1/3` to `ethernet1/4` must be detected as a technical change.
- Distinguish real configuration changes, newly discovered old configurations, and analysis/validation changes.
- Compare previous and current run snapshots only in comparable collection scopes.
- Never treat absence in a failed/partial collection as proof of deletion.
- Preserve historical observations and previously validated site decisions when a source observation disappears.
- Discovery-run metadata and snapshot persistence are future implementation components; architectural requirement is locked, API/storage design not yet implemented.

## Consequences

- Canonical prefix identity can stay stable while route state or egress relationship changes.
- Future DHCP and other collectors use the same repeatable lifecycle.
