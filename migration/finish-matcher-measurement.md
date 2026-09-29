# Finish matcher measurement parity

Source `7055e4e5f64f8e405033509de324f57362868200` introduced the
finishing-color matcher measurement contract. The Web owner is represented by
merged [Web PR #167](https://github.com/MALIEV-Co-Ltd/Legacy.Maliev.Web/pull/167).
The portable event dictionary is in `finish-matcher-measurement-contract.json`.
This record ports the source decision; it does **not** say GTM or GA4 is live.

The six matcher events are consent-gated diagnostics, never GA4 key events,
Google Ads conversions, primary actions, or bidding goals. Only the existing
post-persistence `maliev_lead_submitted` / `generate_lead` path is a lead
outcome. Browser payloads must contain only allowlisted scalar categories. No
screen HEX, HLC/Lab coordinates, Pantone code, image content/name, customer
text, URL query string, or identity field may be sent. In particular,
`has_pantone` reveals only presence, not the supplied value. `step_number`
is an integer from 1 through 10. `match_quality` is `close` for Delta E <= 3,
`noticeable` for Delta E <= 10, or `large_difference` above 10.

The intended funnel is `finish_matcher_viewed` -> `finish_matcher_started` ->
`finish_matcher_quote_clicked` -> consented persisted `generate_lead` in the
same session. The first event requires at least 50% visibility; started and
clicked fire once per page load. Selection events fire only on a changed
recommendation, guidance once per topic per page load, and validation errors
once per failed attempt. Compare activation, handoff, and persisted-lead rates
weekly, segmented by device and locale; track validation-error and weak-match
shares. Do not set a performance target before 28 days of consent-aware
production data.

## Release gates still pending

- Verify exact order and allowlisted payloads in local `dataLayer`, including
  denied consent, and ensure no matcher event dispatches an Ads conversion.
- In GTM, route only the six names to the existing diagnostic quote-funnel GA4
  tag (`CE - diagnostic_quote_funnel` -> `GA4 - diagnostic quote funnel` in
  container `GTM-KHDDLVRR`, measurement ID `G-YYYMMW7P1Z`). Map existing
  `service_id`, `intent`, `locale`, `source`, `step_number`, and
  `failure_category` variables plus new `input_method`, `selection_type`,
  `sheen`, `match_quality`, `guidance_topic`, and `has_pantone` variables.
  Register the five categorical fields and `has_pantone` as event-scoped
  dimensions; `step_number` remains numeric. Do not register matcher events
  as GA4 key events or attach Ads tags.
- Confirm GTM Preview/Tag Assistant and GA4 DebugView, then use natural
  production traffic and GA4 Data API counts to check duplicates and funnel
  ordering. The source recommends an indirect four-step GA4 exploration with
  a 30-minute window and device/locale breakdown. Those external operations
  are not performed by this repository change and need separate release
  evidence.

Web's focused matcher/consent tests are the runtime check. This Workflows
contract test guards the portable event inventory and privacy boundary; it
does not substitute for browser, tag-manager, or production-data verification.
