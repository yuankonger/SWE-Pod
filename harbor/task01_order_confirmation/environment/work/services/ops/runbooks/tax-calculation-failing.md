# TaxCalculationFailing

Core asked the tax app for taxes and could not use the answer. Customers on those checkouts cannot pay.

1. Core's log has one `taxes could not be calculated` line per failure, with the reason.
2. "did not answer": the tax app is down or returned an error. Read the tax app's log.
3. "Number of lines ... doesn't match" or a missing field: the two sides disagree about the answer's format.
   The format is Core's. Find out which side changed, and ask both owners.
