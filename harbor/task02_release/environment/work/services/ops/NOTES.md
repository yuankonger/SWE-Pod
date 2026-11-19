# Monitoring: on-call owner's notes

- Prometheus configuration, alert rules, rule tests and runbooks. `./run test` checks them with promtool.
- The company runs the real Prometheus with `prometheus/prometheus.yml`. The platform writes `targets.json`
  beside it: one target per running service, labelled `service`.
- Every service serves `/metrics`. Core's metric and label names follow Saleor's telemetry (`saleor_graphql_*`,
  `saleor_webhook_*`, `saleor_app_identifier`); the others are `seedco_*` and `http_server_request_count_total`.
- Counters start when a service starts and only appear after their first increment. The rules compare totals
  with thresholds instead of using `increase()`, which would miss a counter's first increment.
- A rule that names a metric or a label nobody exports never fires and never errors. When a service renames a
  metric, the rule that reads it goes quiet.
- The email app answers 200 to events it cannot use, so Core's delivery metrics stay healthy while customers
  get no email. `NotificationsDroppingEvents` is the only alert that sees it.
- Every service logs one JSON object per line: `timestamp`, `level`, `service`, `message`, and attributes.
- Each alert's `runbook` annotation names a file under `runbooks/`.
