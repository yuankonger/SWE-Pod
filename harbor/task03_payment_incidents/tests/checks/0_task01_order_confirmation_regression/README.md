# Regression suite

End-to-end checks of what the company does today and must still do after any change: a paid order gets its
receipt, customers can buy in the web shop and in every supported build of the mobile app, subscriptions renew,
and the orders and subscribers already in the company's history are still handled.

    cd regression && python3 -m unittest -v test_regression

The suite starts the whole company (every service and Prometheus) on ports 7100-7109, from the history each
owner holds under `services/<owner>/data`, and stops it afterwards. It first kills whatever is listening on
those ports. Set `SEEDCO_BASE_PORT` to use other ports.

| File | What it is |
| --- | --- |
| `regression_checks.py` | The checks, one per method |
| `common.py` | Starts the company; buys through Core's API; reads what each system holds |
| `shop.py` | A browser for the web shop and the dashboard: reads pages as HTML, submits forms |
| `replay.ts` | Buys the way one build of the mobile app does |
| `pristine/mobile-1.0.0/` | Release 1.0.0 as it shipped: the build on customers' phones |

These checks do not cover what a change is meant to add. That is judged separately.
