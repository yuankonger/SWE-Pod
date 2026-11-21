We would like one thing added to the API. This is what it should do.

## The feature

Customers are grouped into customer types, the way products are grouped into product types. A customer type has a name and the set of attributes its customers share, and exactly one type is the default. Staff who hold the permission for it can already create and rename types, make a type the default, and assign, reorder and unassign a type's attributes.

**Deleting a customer type.** What is missing is deleting one: a `customerTypeDelete` mutation, beside `customerTypeCreate` and `customerTypeUpdate` and for the same permission. The default type cannot be deleted, even if it only becomes the default while the deletion is under way. Apps are told of a deletion through the `CUSTOMER_TYPE_DELETED` webhook event, which exists already.

It is done when it is on `main` of `core` and works there: the API starts on a fresh database, and the tests the repository has today still pass. `INTERFACE.md` lists the names the project's own tests for this mutation use; keep to them.
