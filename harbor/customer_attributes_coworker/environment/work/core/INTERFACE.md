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

## The API the tests call

The tests call the API by the names below, so the API must have them, spelt and typed as shown. This is all the
feature adds to the API's schema: the new types whole, then what types that exist today gain. Descriptions are
yours to write. `saleor/graphql/schema.graphql` is not updated for you: it must be what the code generates.

```graphql
type CustomerType implements Node & ObjectWithMetadata @doc(category: "Users") {
  id: ID!
  privateMetadata: [MetadataItem!]!
  privateMetafield(key: String!): String
  privateMetafields(keys: [String!]): Metadata
  metadata: [MetadataItem!]!
  metafield(key: String!): String
  metafields(keys: [String!]): Metadata
  name: String!
  slug: String!
  isDefault: Boolean!
  attributes: [Attribute!]
  availableAttributes(where: AttributeWhereInput, search: String, before: String, after: String, first: Int, last: Int): AttributeCountableConnection
}

type CustomerTypeCountableConnection @doc(category: "Users") {
  pageInfo: PageInfo!
  edges: [CustomerTypeCountableEdge!]!
  totalCount: Int
}

type CustomerTypeCountableEdge @doc(category: "Users") {
  node: CustomerType!
  cursor: String!
}

input CustomerTypeWhereInput @doc(category: "Users") {
  metadata: MetadataFilterInput
  ids: [ID!]
  name: StringFilterInput
  slug: StringFilterInput
  isDefault: Boolean
  AND: [CustomerTypeWhereInput!]
  OR: [CustomerTypeWhereInput!]
}

input CustomerTypeSortingInput @doc(category: "Users") {
  direction: OrderDirection!
  field: CustomerTypeSortField!
}

enum CustomerTypeSortField @doc(category: "Users") {
  NAME
  SLUG
}

type CustomerTypeCreate @doc(category: "Users") @webhookEventsInfo(asyncEvents: [CUSTOMER_TYPE_CREATED], syncEvents: []) {
  errors: [CustomerTypeCreateError!]!
  customerType: CustomerType
}

type CustomerTypeCreateError @doc(category: "Users") {
  field: String
  message: String
  code: CustomerTypeCreateErrorCode!
}

enum CustomerTypeCreateErrorCode @doc(category: "Users") {
  GRAPHQL_ERROR
  INVALID
  NOT_FOUND
  REQUIRED
  UNIQUE
}

input CustomerTypeCreateInput @doc(category: "Users") {
  name: String
  slug: String
  isDefault: Boolean
}

type CustomerTypeUpdate @doc(category: "Users") @webhookEventsInfo(asyncEvents: [CUSTOMER_TYPE_UPDATED], syncEvents: []) {
  errors: [CustomerTypeUpdateError!]!
  customerType: CustomerType
}

type CustomerTypeUpdateError @doc(category: "Users") {
  field: String
  message: String
  code: CustomerTypeUpdateErrorCode!
}

enum CustomerTypeUpdateErrorCode @doc(category: "Users") {
  CANNOT_UNSET_DEFAULT
  GRAPHQL_ERROR
  INVALID
  NOT_FOUND
  REQUIRED
  UNIQUE
}

input CustomerTypeUpdateInput @doc(category: "Users") {
  name: String
  slug: String
  isDefault: Boolean
}

type CustomerTypeDelete @doc(category: "Users") @webhookEventsInfo(asyncEvents: [CUSTOMER_TYPE_DELETED], syncEvents: []) {
  errors: [CustomerTypeDeleteError!]!
  customerType: CustomerType
}

type CustomerTypeDeleteError @doc(category: "Users") {
  field: String
  message: String
  code: CustomerTypeDeleteErrorCode!
}

enum CustomerTypeDeleteErrorCode @doc(category: "Users") {
  CANNOT_DELETE_DEFAULT
  GRAPHQL_ERROR
  INVALID
  NOT_FOUND
}

type CustomerTypeAssignAttributes @doc(category: "Users") @webhookEventsInfo(asyncEvents: [CUSTOMER_TYPE_UPDATED], syncEvents: []) {
  customerType: CustomerType
  errors: [CustomerTypeAssignAttributesError!]!
}

type CustomerTypeAssignAttributesError @doc(category: "Users") {
  field: String
  message: String
  code: CustomerTypeAssignAttributesErrorCode!
  attributes: [ID!]
}

enum CustomerTypeAssignAttributesErrorCode @doc(category: "Users") {
  ATTRIBUTE_ALREADY_ASSIGNED
  GRAPHQL_ERROR
  INVALID
  NOT_FOUND
}

type CustomerTypeUnassignAttributes @doc(category: "Users") @webhookEventsInfo(asyncEvents: [CUSTOMER_TYPE_UPDATED], syncEvents: []) {
  customerType: CustomerType
  errors: [CustomerTypeUnassignAttributesError!]!
}

type CustomerTypeUnassignAttributesError @doc(category: "Users") {
  field: String
  message: String
  code: CustomerTypeUnassignAttributesErrorCode!
}

enum CustomerTypeUnassignAttributesErrorCode @doc(category: "Users") {
  GRAPHQL_ERROR
  INVALID
  NOT_FOUND
}

type CustomerTypeReorderAttributes @doc(category: "Users") @webhookEventsInfo(asyncEvents: [CUSTOMER_TYPE_UPDATED], syncEvents: []) {
  customerType: CustomerType
  errors: [CustomerTypeReorderAttributesError!]!
}

type CustomerTypeReorderAttributesError @doc(category: "Users") {
  field: String
  message: String
  code: CustomerTypeReorderAttributesErrorCode!
  attributes: [ID!]
}

enum CustomerTypeReorderAttributesErrorCode @doc(category: "Users") {
  GRAPHQL_ERROR
  INVALID
  NOT_FOUND
}

type CustomerTypeCreated implements Event @doc(category: "Users") {
  issuedAt: DateTime
  version: String
  issuingPrincipal: IssuingPrincipal
  recipient: App
  customerType: CustomerType
}

type CustomerTypeUpdated implements Event @doc(category: "Users") {
  issuedAt: DateTime
  version: String
  issuingPrincipal: IssuingPrincipal
  recipient: App
  customerType: CustomerType
}

type CustomerTypeDeleted implements Event @doc(category: "Users") {
  issuedAt: DateTime
  version: String
  issuingPrincipal: IssuingPrincipal
  recipient: App
  customerType: CustomerType
}
```

Added to types that exist today:

```graphql
type AccountError {
  # ...what it has today, and:
  attributes: [ID!]
}

enum AttributeTypeEnum {
  # ...what it has today, and:
  CUSTOMER_TYPE
}

type CustomerBulkUpdateError {
  # ...what it has today, and:
  attributes: [ID!]
}

input CustomerInput {
  # ...what it has today, and:
  customerType: ID
  attributes: [AttributeValueInput!]
}

input CustomerWhereInput {
  # ...what it has today, and:
  customerType: GlobalIDFilterInput
  attributes: [AssignedAttributeWhereInput!]
}

type Mutation {
  # ...what it has today, and:
  customerTypeCreate(input: CustomerTypeCreateInput!): CustomerTypeCreate @doc(category: "Users") @webhookEventsInfo(asyncEvents: [CUSTOMER_TYPE_CREATED], syncEvents: [])
  customerTypeUpdate(id: ID!, input: CustomerTypeUpdateInput!): CustomerTypeUpdate @doc(category: "Users") @webhookEventsInfo(asyncEvents: [CUSTOMER_TYPE_UPDATED], syncEvents: [])
  customerTypeDelete(id: ID!): CustomerTypeDelete @doc(category: "Users") @webhookEventsInfo(asyncEvents: [CUSTOMER_TYPE_DELETED], syncEvents: [])
  customerTypeAssignAttributes(attributeIds: [ID!]!, customerTypeId: ID!): CustomerTypeAssignAttributes @doc(category: "Users") @webhookEventsInfo(asyncEvents: [CUSTOMER_TYPE_UPDATED], syncEvents: [])
  customerTypeUnassignAttributes(attributeIds: [ID!]!, customerTypeId: ID!): CustomerTypeUnassignAttributes @doc(category: "Users") @webhookEventsInfo(asyncEvents: [CUSTOMER_TYPE_UPDATED], syncEvents: [])
  customerTypeReorderAttributes(customerTypeId: ID!, moves: [ReorderInput!]!): CustomerTypeReorderAttributes @doc(category: "Users") @webhookEventsInfo(asyncEvents: [CUSTOMER_TYPE_UPDATED], syncEvents: [])
}

enum PermissionEnum {
  # ...what it has today, and:
  MANAGE_CUSTOMER_TYPES_AND_ATTRIBUTES
}

type Query {
  # ...what it has today, and:
  customerType(id: ID!): CustomerType @doc(category: "Users")
  customerTypes(where: CustomerTypeWhereInput, search: String, sortBy: CustomerTypeSortingInput, before: String, after: String, first: Int, last: Int): CustomerTypeCountableConnection @doc(category: "Users")
}

type StaffError {
  # ...what it has today, and:
  attributes: [ID!]
}

type User {
  # ...what it has today, and:
  assignedAttribute(slug: String!): AssignedAttribute
  assignedAttributes(limit: PositiveInt = 100): [AssignedAttribute!]!
  customerType: CustomerType
}

input UserCreateInput {
  # ...what it has today, and:
  customerType: ID
  attributes: [AttributeValueInput!]
}

enum WebhookEventTypeAsyncEnum {
  # ...what it has today, and:
  CUSTOMER_TYPE_CREATED
  CUSTOMER_TYPE_UPDATED
  CUSTOMER_TYPE_DELETED
}

enum WebhookEventTypeEnum {
  # ...what it has today, and:
  CUSTOMER_TYPE_CREATED
  CUSTOMER_TYPE_UPDATED
  CUSTOMER_TYPE_DELETED
}

enum WebhookSampleEventTypeEnum {
  # ...what it has today, and:
  CUSTOMER_TYPE_CREATED
  CUSTOMER_TYPE_UPDATED
  CUSTOMER_TYPE_DELETED
}
```

## What the tests check to the letter

Behaviour the hidden tests assert exactly, which the description of the feature does not settle.

- `saleor/graphql/schema.graphql` is the public API contract and is as it is today, without the feature. Bring it up to date from the code (`python manage.py get_graphql_schema > saleor/graphql/schema.graphql`): the schema the code generates must equal it. What the feature adds to the API is listed above, under "The API the tests call".
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
- A user whose `customer_type` is null (one the backfill has not reached) is treated everywhere as having the default customer type, and stays null until a type is set: `User.customerType` gives the default type; `User.assignedAttributes` and the validation of attribute input use the default type's attributes; filtering customers by the default type (`customerType: {eq: ...}` or `{oneOf: [...]}`) or by an attribute of the default type includes such users. A mutation that sets only such a user's attributes (`customerBulkUpdate`, say) accepts values for the default type's attributes and leaves `customer_type` null.
- The `customerType` and `customerTypes` queries are open to any staff user and any app, whatever permissions they hold, and to nobody else: a customer or an anonymous request gets a permission error. `CustomerType.attributes` lists all of the type's attributes to holders of `MANAGE_USERS` or `MANAGE_CUSTOMER_TYPES_AND_ATTRIBUTES`, and only those visible in the storefront to everyone else.
- `User.customerType` and `User.assignedAttributes` can be read by the user themself and by holders of `MANAGE_USERS`; anyone else who can reach the user (staff with `MANAGE_ORDERS` or `MANAGE_STAFF` only, say) gets a permission error on the field.
- Changing a customer's type keeps the values the customer has for attributes the new type lacks: the rows stay in the database.
- `customerTypeReorderAttributes` with the id of a customer type that does not exist gives one error on `customerTypeId` with code `NOT_FOUND` and the message "Couldn't resolve to a customer type: <id>".
- The `translation` query for a value of a customer attribute (kind `ATTRIBUTE_VALUE`) returns null.
