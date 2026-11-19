# What the hidden tests rely on

The work is judged by the project's own tests, which you cannot see. They use the names below. Each must
exist at exactly this place under exactly this name, declared as shown (every parameter and property), or
the tests that use it cannot run. This says where things live and what they are called, not what they do.

## Names that do not exist yet

### `saleor.account.error_codes`
- `CustomerTypeAssignAttributesErrorCode`: `class CustomerTypeAssignAttributesErrorCode(Enum)`
- `CustomerTypeCreateErrorCode`: `class CustomerTypeCreateErrorCode(Enum)`
- `CustomerTypeDeleteErrorCode`: `class CustomerTypeDeleteErrorCode(Enum)`
- `CustomerTypeReorderAttributesErrorCode`: `class CustomerTypeReorderAttributesErrorCode(Enum)`
- `CustomerTypeUnassignAttributesErrorCode`: `class CustomerTypeUnassignAttributesErrorCode(Enum)`
- `CustomerTypeUpdateErrorCode`: `class CustomerTypeUpdateErrorCode(Enum)`

### `saleor.account.exceptions`  (new module)
- `NoDefaultCustomerType`: `class NoDefaultCustomerType(Exception)`

### `saleor.account.migrations.tasks.saleor3_23`
- `assign_default_customer_type_to_users_task`: `def assign_default_customer_type_to_users_task()`

### `saleor.account.models`
- `CustomerType`: `class CustomerType(ModelWithMetadata)`

### `saleor.account.utils`
- `get_default_customer_type`: `def get_default_customer_type(database_connection_name: str=settings.DATABASE_CONNECTION_DEFAULT_NAME)`

### `saleor.attribute.models`
- `AssignedUserAttributeValue`: `class AssignedUserAttributeValue(SortableModel)`
- `AttributeCustomerType`: `class AttributeCustomerType(SortableModel)`

### `saleor.graphql.account.mutations.customer_type.customer_type_create`  (new module)
- `customer_type_qs_select_for_update`: `def customer_type_qs_select_for_update()`

### `saleor.graphql.account.sorters`
- `CustomerTypeSortField`: `class CustomerTypeSortField(BaseEnum)`

## What the tests check to the letter

Behaviour the hidden tests assert exactly, which the description of the feature does not settle.

- `saleor/graphql/schema.graphql` is already as it is once the feature is done. It is the public API contract: every type, field, input, mutation, enum value and error code the feature adds is in it, and the schema the code generates must equal it.
- At most one customer type is the default, enforced in the database by a unique constraint named `unique_default_customer_type`.
- `User.customer_type` is a nullable foreign key that protects: deleting a customer type that a user has raises Django's `ProtectedError`.
- `assign_default_customer_type_to_users_task` raises `NoDefaultCustomerType` when no default customer type exists.
- `customerTypeCreate` with neither `name` nor `slug` returns two errors, one for `name` and one for `slug`, each with code `REQUIRED`.
- Making a type the default clears the flag on whichever type holds it, including one the locking query (`customer_type_qs_select_for_update`) did not return.
- `customerTypeAssignAttributes` and `customerTypeUnassignAttributes` take at most 100 ids. More gives one error on `attributeIds` with code `INVALID` and the message "Cannot assign more than 100 attributes in a single mutation." ("Cannot unassign more than ..." for unassign).
- `customerTypeAssignAttributes` with any id that does not exist assigns nothing and gives one error on `attributeIds` with code `NOT_FOUND`, the message "Some of the attributes do not exist." and the missing ids in `attributes`.
- A `customerType` id of another type (say a `PageType` id) gives code `GRAPHQL_ERROR` on `customerType`. In `customerBulkUpdate` the error's path is `input.customerType` and its message "Invalid ID: <id>. Expected: CustomerType, received: PageType."
- On `customerCreate`, an attribute that is not assigned to the customer's type gives one error on `attributes` with code `NOT_FOUND` and the message "Could not resolve attributes: ID: <id>."
- `customerBulkUpdate` that changes only a customer's attributes still calls the `customer_updated` webhook for that customer.
- A reference value of a customer attribute is a row of its own per user (slug `<user pk>_<referenced object pk>`), never shared between users. Deleting a user deletes that user's rows and leaves the other users' rows and the referenced object.
- In the shared attribute where-filter, a reference container with neither `containsAny` nor `containsAll` (for example `{pageSlugs: {}}`) matches nothing. This holds for products and variants too.
- Translating a value of a customer attribute is refused with code `INVALID` and the message "Values of customer attributes cannot be translated.": on field `id` in `attributeValueTranslate`, on path `id` in `attributeValueBulkTranslate` (the other rows of the call still go through).
- A customer type's attributes are a many-to-many `Attribute.customer_types` (to `CustomerType`, `related_name="customer_attributes"`) through `AttributeCustomerType`, whose fields are `attribute` and `customer_type` (both `related_name="attributecustomertype"`). So `customer_type.customer_attributes` is the attributes of a type.
- `AssignedUserAttributeValue` has the fields `value` (to `AttributeValue`, `related_name="uservalueassignment"`) and `user` (to `User`, `related_name="attributevalues"`); `(value, user)` is unique.
- `saleor.attribute.utils.associate_attribute_values_to_instance` takes a `User` as the instance too, as it takes a `Product`, `ProductVariant` or `Page`.
- `PluginsManager` has `customer_type_created(customer_type)`, `customer_type_updated(customer_type)` and `customer_type_deleted(customer_type, webhooks=None)`, which the mutations call; the tests patch them.
- `saleor.account.migrations.tasks.saleor3_23.ASSIGN_DEFAULT_CUSTOMER_TYPE_BATCH_SIZE` is the batch size of `assign_default_customer_type_to_users_task` (100).
- The default customer type the migrations create is named "Default" with the slug "default".
