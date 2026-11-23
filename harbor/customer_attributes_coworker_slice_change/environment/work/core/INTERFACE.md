# What the hidden tests rely on

The work is judged by the project's own tests, which you cannot see. They use the names below. Each must
exist at exactly this place under exactly this name, declared as shown (every parameter and property), or
the tests that use it cannot run. This says where things live and what they are called, not what they do.

## The API the tests call

The tests call the API by the names below, so the API must have them, spelt and typed as shown. This is all the
feature adds to the API's schema: the new types whole, then what types that exist today gain. Descriptions are
yours to write. `saleor/graphql/schema.graphql` is not updated for you: it must be what the code generates.

```graphql
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
```

Added to types that exist today:

```graphql
type Mutation {
  # ...what it has today, and:
  customerTypeDelete(id: ID!): CustomerTypeDelete @doc(category: "Users") @webhookEventsInfo(asyncEvents: [CUSTOMER_TYPE_DELETED], syncEvents: [])
}
```

## What the tests check to the letter

Behaviour the hidden tests assert exactly, which the description of the feature does not settle.

- `saleor/graphql/schema.graphql` is the public API contract and is as it is today, without the mutation. Bring it up to date from the code (`python manage.py get_graphql_schema > saleor/graphql/schema.graphql`): the schema the code generates must equal it. What the work adds to the API is listed above, under "The API the tests call".
- `PluginsManager.customer_type_deleted(customer_type, webhooks=None)` exists already; the mutation calls it once the type is deleted, and the tests patch it.
- The error type's codes are `saleor.account.error_codes.CustomerTypeDeleteErrorCode`, which exists already; deleting the default type gives `CANNOT_DELETE_DEFAULT` on field `id`.
