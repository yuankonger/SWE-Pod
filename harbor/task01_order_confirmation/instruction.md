Change OPS-7: from now on, an order placed in a shop waits for a member of staff to confirm it before it is fulfilled. Core owns the change and decides how it works. When it is done, customers must still be able to buy in the web shop and in every supported build of the mobile app, and renewals must keep flowing.

The whole company is yours to change. The decision record is at `/work/services/core/docs/OPS-7.md`. Implement it everywhere it applies and keep every owner's tests passing (update them to the new behaviour).

The company's code is in `/work/services`. Its end-to-end regression tests are in `/work/regression`. A hidden
suite decides whether the work is right.
