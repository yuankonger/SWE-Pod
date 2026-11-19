We would like one feature built. It may need changes in more than one repository.

## The feature

Staff can record structured details about customers, such as a tax ID, an account manager or a contract tier, as attributes. Until now attributes could be given to products and pages only.

**Customer types.** Customers are grouped into customer types, the way products are grouped into product types. A customer type has a name and the set of attributes its customers share. Exactly one type is the default, and a customer created without a type, by whatever route, gets it. Staff who hold the permission for it can create, rename and delete types, make a type the default, and assign, reorder and unassign a type's attributes, with a limit on how many in one request. The default type cannot be deleted, even if it only becomes the default while the deletion is under way. Apps are told of changes to customer types through webhook events.

**Attributes on customers.** Creating or updating a customer, one at a time or in bulk, can set the customer's type and values for that type's attributes. When a bulk update fails on attributes, its errors say which. The list of customers can be filtered by type and by attribute values, as products and pages can. Values that belong to one customer alone are deleted with that customer. Values of customer attributes cannot be translated. Managing customer attributes takes the customer-type permission, not the product or page one, and a request that touches attributes of several kinds needs the permission for each.

**In the staff application.**

1. Configuration has a new **Customers** section with **Customer types** and **Customer attributes**. Types can be created, renamed, given a default, and have attributes assigned, reordered or unassigned, the same way product and model types work.
2. On a customer's profile staff can pick the type and fill in its attributes (each under its name, with a control for its value, saved with the rest of the page), and jump to the type's settings from the attributes card. The type also appears as a badge in the profile header, linking to that type's tab on the customer list. The customer list has a tab per type, as models do.
3. The customer's page is reorganised around this: the header carries status, type and member-since; the main column shows order figures per channel, recent orders, and attributes; contact details, addresses, external reference and gift cards sit in the sidebar. A recent order's whole row is clickable.
4. Customer types are in the Customers sidebar. Open **Customers** to jump to **All**, or to a type such as **B2B** or **Default**. **Customer Types** at the bottom opens the type settings. If there is only one type, the menu stays **All** plus settings. Types pinned on the customer list appear first, and only a handful are listed so the menu stays short.
5. Customers can be filtered by attributes: on the customer list, open **Conditions** and choose **Attribute**. Filter menus show more choices and load more on scroll.

It is done when it is on `main` of both repositories and works there: the API starts on a fresh database, and staff can do in the staff application what the feature is for. The tests each repository has today should still pass. Each repository's `INTERFACE.md` lists the names the project's own tests for this feature use; keep to them.
