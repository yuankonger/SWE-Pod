We would like one feature built in the API. This is what it should do.

## The feature

Staff can record structured details about customers, such as a tax ID, an account manager or a contract tier, as attributes. Until now attributes could be given to products and pages only.

**Customer types.** Customers are grouped into customer types, the way products are grouped into product types. A customer type has a name and the set of attributes its customers share. Exactly one type is the default, and a customer created without a type, by whatever route, gets it. Staff who hold the permission for it can create, rename and delete types, make a type the default, and assign, reorder and unassign a type's attributes, with a limit on how many in one request. The default type cannot be deleted, even if it only becomes the default while the deletion is under way. Apps are told of changes to customer types through webhook events.

**Attributes on customers.** Creating or updating a customer, one at a time or in bulk, can set the customer's type and values for that type's attributes. When a bulk update fails on attributes, its errors say which. The list of customers can be filtered by type and by attribute values, as products and pages can. Values that belong to one customer alone are deleted with that customer. Values of customer attributes cannot be translated. Managing customer attributes takes the customer-type permission, not the product or page one, and a request that touches attributes of several kinds needs the permission for each.

It is done when it is on `main` of `core` and works there: the API starts on a fresh database, and the tests the repository has today still pass. `INTERFACE.md` lists the names the project's own tests for this feature use; keep to them.
