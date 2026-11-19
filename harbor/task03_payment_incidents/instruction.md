Release 2026.11 went out a week ago. Since then three reports have come in, and nobody has found the cause of any of them.

1. Finance: on some orders the payment provider's records show more money paid back than staff asked for. On the same orders the dashboard shows a refund as failed. On most of them staff had refunded the same amount twice; on one, staff asked once, for an amount never refunded on that order before.
2. Warehouse: one subscriber was sent a new box on three days running. Support stopped it by cancelling the subscription.
3. Support: over those three days several subscribers' monthly boxes were not created. They were created on the fourth day.

Find what is wrong and fix it, in whichever systems it takes. Finance also needs to know the damage from report 1: write `/work/services/payments/docs/over-refunds.csv` with the header `order_number,overpaid` and one line for each order on which the provider paid back more than staff asked for, giving the order's number and the amount overpaid in dollars. The databases you can query hold what happened that week, and each system's log of that week is in its `logs/production.log`. Everything customers and staff can do today must keep working, including what release 2026.11 added: it is not to be taken out.

The whole company is yours to change. Keep every owner's tests passing.

The company's code is in `/work/services`. Its end-to-end regression tests are in `/work/regression`. A hidden
suite decides whether the work is right.
