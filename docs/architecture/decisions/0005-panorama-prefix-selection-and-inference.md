# 0005 - Use Panorama connected and selected static routes as site-discovery inputs

## Status

Accepted

## Context

Only a minority of Panorama connected prefixes matched site scopes built from BGP and inventory. Static routes can expose local networks missing from the BGP source, but may also reach remote sites.

## Decision

- Use non-tunnel connected interface networks as discovery inputs across virtual routers.
- Use static route destination networks only from VR `vpn_intern` when an outgoing interface exists and is not a tunnel.
- Exclude `/0`–`/12` and `/32` from automatic site ownership; retain observations as source data.
- Connected `/13`–`/19` require validation, connected `/20`–`/31` can be eligible; static `/13`–`/31` are discovery/validation candidates.
- Do not equate a non-tunnel static-route egress with exclusive local ownership.
- When sufficiently supported site context is **one** site, propose unassigned prefixes for that site, respecting confidence policy.
- When a firewall has evidence for **multiple** sites, propose an unassigned supernet for **each** associated site as a `candidate`, not validated ownership.
- Later more-specific prefixes can be associated/validated for one site while a broader shared candidate remains.
- Preserve the observation interface/next hop/VR for correlation and later change detection.

## Consequences

- SITE-A `10.1.0.0/24` and `10.1.31.0/24` were explicitly confirmed by the user as belonging to `SITE-A` (a fact to record as validation input, not a general automatic rule).
- Shared route destinations remain possible candidates, without contaminating scope attribution.
