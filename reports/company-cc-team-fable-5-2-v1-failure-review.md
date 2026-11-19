# Fable team v1: failure review

Review of recorded judge outputs and agent tool-call trajectory; no replay or full test rerun. No final repository snapshot/patch is present among this trial's artifacts, so some runtime diagnoses remain provisional.

## Run result and rubric version

Reward 0.9311. Core 198/203 feature tests, dashboard 74/105 scored feature tests, diagnostic helpers 49/79. All 17,535 core and 5,568 dashboard regression identities passed. All three contract fits and both browser workflows passed. This run uses a newer rubric than the earlier task review: saving a tier is a target with weight 1, core tests weight 1, dashboard tests weight 0.5. The weighted progress is (0.9754 + 0.5*0.7048 + 1)/2.5 = 0.93112.

Both agents terminate with provider HTTP 429 errors. The transcript records two coordination messages agreeing on the schema. Core copied page filtering/dataloader code and renamed page-type references to customer-type references; that adaptation omitted the legacy-null/default-type behavior. Dashboard retained substantial existing customer components while adding types/attributes. Treat this as an interrupted implementation, not a completed run demonstrating a capability ceiling.

## Attribution

- Core's five failures: implementation omissions. Bulk staff deletion leaves owned values; attribute filtering and assignedAttributes omit default-type fallback for null user.customer_type; single/list translation queries expose customer attribute values. The mutation restriction alone does not cover translation discovery.
- Four customer queryVariables assertions: test shape coupling. Top-level predicates are applied sequentially by WhereFilterSet.filter_queryset, so those conjunctive inputs need not be wrapped in AND; missing OR: undefined is not a wire-level difference. This does not establish correctness for all arbitrary OR expressions.
- AssignedAttributeQueryVarsBuilder numeric-range assertion: test overconstraint for the observed case. Decimal.parse_value converts strings through decimal.Decimal, so "10" versus 10 is accepted by Core. In contrast, CustomerNumberOfOrdersQueryVarsBuilder emits gte/lte at the wrong level, without IntFilterInput.range: a real implementation error.
- Title status test IDs (2), configuration Customers-group position (1), disabled versus hidden default-type delete (1), and savebar versus menu placement of delete (1): mainly UI structure/presentation coupling. The observed DOM has the statuses/disabled action; absence of the expected structure alone is not evidence of broken business behavior.
- MANAGE_STAFF disabled-field assertion: test selects a Material UI wrapper div, then calls toBeDisabled. Its helper explicitly assumes a Macaw native input. Inspect the descendant input before attributing a permissions bug.
- Seven CustomerDetailsPage render crashes: likely a shared import/mock mismatch, not seven independent permission bugs. The hidden test mocks ../CustomerOrders/CustomerOrders with only a named CustomerOrders export; the base page imports CustomerOrders as default through the barrel, and the recorded page-edit command retains that import. This fits the invalid object element when the orders section renders. The named export is explicitly required by INTERFACE.md, so the submission has a contract problem, but these tests do not establish a production render or permissions bug. Confirm against the exact final tree with a dual-export mock before assigning additional behavioral failures.
- CustomerOrders tests (3): named component resolves to undefined. INTERFACE.md requires a named CustomerOrders export, making this a submission-contract violation, but these tests do not establish that the production recent-orders view fails (existing code can import a default export).
- WarehouseHandler pagination: dropping after on a next-page request is a genuine omission; exact first=20 versus first=5 in the other tests is partly a policy/implementation detail.
- CustomerAddresses loading: observed output says the customer has no addresses while loading. This is a genuine misleading state, beyond a missing test ID.
- CustomerAttributesCard and CustomerListPage: mixed. Permission-sensitive controls remain rendered and the type chip lacks its expected link; these merit implementation fixes, but UI visibility is not evidence of an API authorization bypass. Missing type-option selector alone does not prove that reverting a type is broken.
- 30 nonpassing helper cases do not reduce this run's reward. Eleven come from a missing createCustomerTypeMenuItems module; the rest mix exact helper contracts, snapshot structure and potentially real selection/rehydration/navigation defects. They should not all be labeled either product bugs or test bugs.

## Recommended adjudication

Keep the core failures, malformed order-count filter, missing cursor handling and misleading loading state as implementation findings. Replace exact filter-object and decimal-representation comparisons with API-semantic checks. Replace wrapper/test-ID-specific UI assertions with role/label/native-control assertions. Resolve CustomerDetailsPage crashes against the actual final commit before assigning blame. Preserve the provider interruption as a separate infrastructure qualification.

## Recorded failures

### Core: test_deletes_unique_attribute_values_and_keeps_shared_choices

saleor.graphql.account.tests.bulk_mutations.test_staff_bulk_delete

```text
users]
        }
    
        # when
        response = staff_api_client.post_graphql(
            STAFF_BULK_DELETE_MUTATION, variables, permissions=[permission_manage_staff]
        )
    
        # then: the unique values are deleted with the users, the shared choice stays
        content = get_graphql_content(response)
        assert content["data"]["staffBulkDelete"]["count"] == len(staff_users)
        assert (
            User.objects.filter(pk__in=[user.pk for user in staff_users]).exists() is False
        )
>       assert (
            AttributeValue.objects.filter(
                pk__in=[value.pk for value in unique_values]
            ).exists()
            is False
        )
E       assert True is False
E        +  where True = exists()
E        +    where exists = <QuerySet [<AttributeValue: Notes about staff member 109>, <AttributeValue: Notes about staff member 110>]>.exists
E        +      where <QuerySet [<AttributeValue: Notes about staff member 109>, <AttributeValue: Notes about staff member 110>]> = filter(pk__in=[259, 260])
E        +        where filter = <saleor.attribute.models.base.AttributeValueManager object at 0xffff99399190>.filter
E        +          where <saleor.attribute.models.base.AttributeValueManager object at 0xffff99399190> = AttributeValue.objects

saleor/graphql/account/tests/bulk_mutations/test_staff_bulk_delete.py:432: AssertionError
```

### Core: test_filter_matches_users_without_customer_type_via_default_type

saleor.graphql.account.tests.queries.test_customers_where_attributes

```text
omer_users,
        default_customer_type,
        loyalty_customer_attribute,
    ):
        # given: the attribute belongs to the default customer type and the
        # customer has no customer type explicitly assigned
        permission_group_manage_users.user_set.add(staff_api_client.user)
        default_customer_type.customer_attributes.add(loyalty_customer_attribute)
        customer = customer_users[0]
        customer.customer_type = None
        customer.save(update_fields=["customer_type"])
        value = loyalty_customer_attribute.values.get(slug="gold")
        associate_attribute_values_to_instance(
            customer, {loyalty_customer_attribute.pk: [value]}
        )
        variables = {
            "where": {
                "attributes": [
                    {
                        "slug": loyalty_customer_attribute.slug,
                        "value": {"slug": {"eq": value.slug}},
                    }
                ]
            }
        }
    
        # when
        response = staff_api_client.post_graphql(QUERY_CUSTOMERS_WITH_WHERE, variables)
    
        # then
        content = get_graphql_content(response)
        customers = content["data"]["customers"]["edges"]
>       assert len(customers) == 1
E       assert 0 == 1
E        +  where 0 = len([])

saleor/graphql/account/tests/queries/test_customers_where_attributes.py:577: AssertionError
```

### Core: test_assigned_attributes_fall_back_to_default_customer_type

saleor.graphql.account.tests.queries.test_user_assigned_attributes

```text
>
segment_customer_attribute = <Attribute: Segment>

    def test_assigned_attributes_fall_back_to_default_customer_type(
        staff_api_client,
        permission_manage_users,
        customer_user,
        default_customer_type,
        segment_customer_attribute,
    ):
        # given: the user has no customer type assigned yet
        default_customer_type.customer_attributes.add(segment_customer_attribute)
        customer_user.customer_type = None
        customer_user.save(update_fields=["customer_type"])
        variables = {"id": graphene.Node.to_global_id("User", customer_user.pk)}
    
        # when
        response = staff_api_client.post_graphql(
            USER_ASSIGNED_ATTRIBUTES_QUERY,
            variables,
            permissions=[permission_manage_users],
        )
    
        # then
        content = get_graphql_content(response)
        assigned_attributes = content["data"]["user"]["assignedAttributes"]
        slugs = {entry["attribute"]["slug"] for entry in assigned_attributes}
>       assert slugs == {segment_customer_attribute.slug}
E       AssertionError: assert set() == {'segment'}
E         
E         Extra items in the right set:
E         'segment'
E         
E         Full diff:
E         + set()
E         - {
E         -     'segment',
E         - }

saleor/graphql/account/tests/queries/test_user_assigned_attributes.py:174: AssertionError
```

### Core: test_translation_query_customer_attribute_value_returns_null

saleor.graphql.translations.tests.test_translations

```text
staff_api_client = <saleor.graphql.tests.fixtures.ApiClient object at 0xffff62902a20>
loyalty_customer_attribute = <Attribute: Loyalty level>
permission_manage_translations = <Permission: Site | site settings | Manage translations.>

    def test_translation_query_customer_attribute_value_returns_null(
        staff_api_client,
        loyalty_customer_attribute,
        permission_manage_translations,
    ):
        # given
        customer_value = loyalty_customer_attribute.values.first()
        variables = {
            "id": graphene.Node.to_global_id("AttributeValue", customer_value.id),
            "kind": TranslatableKinds.ATTRIBUTE_VALUE.name,
            "languageCode": LanguageCodeEnum.PL.name,
        }
    
        # when
        response = staff_api_client.post_graphql(
            QUERY_TRANSLATION_ATTRIBUTE_VALUE,
            variables,
            permissions=[permission_manage_translations],
        )
    
        # then
        content = get_graphql_content(response)
>       assert content["data"]["translation"] is None
E       AssertionError: assert {'__typename': 'AttributeValueTranslatableContent', 'attributeValueId': 'QXR0cmlidXRlVmFsdWU6MzQyNA==', 'id': 'QXR0cmlidXRlVmFsdWVUcmFuc2xhdGFibGVDb250ZW50OjM0MjQ=', 'name': 'Gold', ...} is None

saleor/graphql/translations/tests/test_translations.py:3458: AssertionError
```

### Core: test_translations_query_excludes_customer_attribute_values

saleor.graphql.translations.tests.test_translations

```text
  id
                        }
                    }
                }
                totalCount
            }
        }
        """
    
        # when
        response = staff_api_client.post_graphql(
            query,
            {"kind": TranslatableKinds.ATTRIBUTE_VALUE.name},
            permissions=[permission_manage_translations],
        )
    
        # then exactly the catalog values are listed, the customer values are not
        data = get_graphql_content(response)["data"]["translations"]
        returned_ids = {edge["node"]["id"] for edge in data["edges"]}
>       assert returned_ids == catalog_value_ids
E       AssertionError: assert {'QXR0cmlidXR...ZW50OjM0NzE='} == {'QXR0cmlidXR...ZW50OjM0Njk='}
E         
E         Extra items in the left set:
E         'QXR0cmlidXRlVmFsdWVUcmFuc2xhdGFibGVDb250ZW50OjM0NzE='
E         'QXR0cmlidXRlVmFsdWVUcmFuc2xhdGFibGVDb250ZW50OjM0NzA='
E         
E         Full diff:
E           {
E               'QXR0cmlidXRlVmFsdWVUcmFuc2xhdGFibGVDb250ZW50OjM0Njc=',
E               'QXR0cmlidXRlVmFsdWVUcmFuc2xhdGFibGVDb250ZW50OjM0Njg=',
E               'QXR0cmlidXRlVmFsdWVUcmFuc2xhdGFibGVDb250ZW50OjM0Njk=',
E         +     'QXR0cmlidXRlVmFsdWVUcmFuc2xhdGFibGVDb250ZW50OjM0NzA=',
E         +     'QXR0cmlidXRlVmFsdWVUcmFuc2xhdGFibGVDb250ZW50OjM0NzE=',
E           }

saleor/graphql/translations/tests/test_translations.py:3503: AssertionError
```

### Dashboard: isMenuActive with customer type shortcuts marks only the shortcut matching the selected customer type

/tmp/seedco-score/dashboard/src/components/Sidebar/menu/utils.test.ts

```text
Error: expect(received).toBe(expected) // Object.is equality

Expected: false
Received: true

```

### Dashboard: isMenuActive with customer type shortcuts does not mark any type shortcut on the unfiltered customer list

/tmp/seedco-score/dashboard/src/components/Sidebar/menu/utils.test.ts

```text
Error: expect(received).toBe(expected) // Object.is equality

Expected: false
Received: true

```

### Dashboard: isMenuActive with customer type shortcuts marks All only on the unfiltered customer list

/tmp/seedco-score/dashboard/src/components/Sidebar/menu/utils.test.ts

```text
Error: expect(received).toBe(expected) // Object.is equality

Expected: false
Received: true

```

### Dashboard: AssignedAttributeQueryVarsBuilder should map numeric ranges to value.numeric.range

/tmp/seedco-score/dashboard/src/components/ConditionalFilter/FiltersQueryBuilder/queryVarsBuilders/AssignedAttributeQueryVarsBuilder.test.ts

```text
Error: expect(received).toEqual(expected) // deep equality

- Expected  - 2
+ Received  + 2

@@ -3,12 +3,12 @@
      Object {
        "slug": "credit-limit",
        "value": Object {
          "numeric": Object {
            "range": Object {
-             "gte": 10,
-             "lte": 20,
+             "gte": "10",
+             "lte": "20",
            },
          },
        },
      },
    ],

```

### Dashboard: CustomerNumberOfOrdersQueryVarsBuilder updateWhereQueryVariables should create an IntFilterInput range from a tuple value

/tmp/seedco-score/dashboard/src/components/ConditionalFilter/FiltersQueryBuilder/queryVarsBuilders/CustomerNumberOfOrdersQueryVarsBuilder.test.ts

```text
Error: expect(received).toEqual(expected) // deep equality

- Expected  - 4
+ Received  + 2

  Object {
-   "range": Object {
-     "gte": 5,
-     "lte": 10,
-   },
+   "gte": "5",
+   "lte": "10",
  }

```

### Dashboard: ConditionalFilter / ValueProvider / TokenArray should create filter container from a given response

/tmp/seedco-score/dashboard/src/components/ConditionalFilter/ValueProvider/TokenArray/TokenArray.test.ts

```text
Error: expect(received).toMatchSnapshot()

Snapshot name: `ConditionalFilter / ValueProvider / TokenArray should create filter container from a given response 1`

- Snapshot  - 7
+ Received  + 1

@@ -65,17 +65,11 @@
            "label": "is",
            "type": "select",
            "value": "input-5",
          },
          "loading": false,
-         "options": Array [
-           Object {
-             "label": "Channel PLN",
-             "slug": "channel-pln",
-             "value": "channel-pln",
-           },
-         ],
+         "options": Array [],
          "value": Object {
            "label": "Channel PLN",
            "slug": "channel-pln",
            "value": "channel-pln",
          },

```

### Dashboard: ConditionalFilter / ValueProvider / TokenArray creates filter container with removing constrain if there is no depepdent rows

/tmp/seedco-score/dashboard/src/components/ConditionalFilter/ValueProvider/TokenArray/TokenArray.test.ts

```text
Error: expect(received).toMatchSnapshot()

Snapshot name: `ConditionalFilter / ValueProvider / TokenArray creates filter container with removing constrain if there is no depepdent rows 1`

- Snapshot  - 7
+ Received  + 1

@@ -16,17 +16,11 @@
            "label": "is",
            "type": "select",
            "value": "input-5",
          },
          "loading": false,
-         "options": Array [
-           Object {
-             "label": "Channel PLN",
-             "slug": "channel-pln",
-             "value": "channel-pln",
-           },
-         ],
+         "options": Array [],
          "value": Object {
            "label": "Channel PLN",
            "slug": "channel-pln",
            "value": "channel-pln",
          },

```

### Dashboard: includeSelectedComboboxOptions keeps fetched options when the selected slug is already present

/tmp/seedco-score/dashboard/src/components/ConditionalFilter/UI/resolveAsyncComboboxState.test.ts

```text
Error: expect(received).toEqual(expected) // deep equality

- Expected  - 0
+ Received  + 5

@@ -1,9 +1,14 @@
  Array [
    Object {
      "label": "Retail",
      "slug": "retail",
+     "value": "retail",
+   },
+   Object {
+     "label": "Retail",
+     "slug": "retail",
      "value": "Q3VzdG9tZXJUeXBlOjE=",
    },
    Object {
      "label": "VIP",
      "slug": "vip",

```

### Dashboard: resolveComboboxValue uses the fetched option so the combobox value matches the list identity

/tmp/seedco-score/dashboard/src/components/ConditionalFilter/UI/resolveAsyncComboboxState.test.ts

```text
Error: expect(received).toEqual(expected) // deep equality

- Expected  - 1
+ Received  + 1

  Object {
    "label": "Retail",
    "slug": "retail",
-   "value": "Q3VzdG9tZXJUeXBlOjE=",
+   "value": "retail",
  }

```

### Dashboard: CustomerAddresses shows a skeleton while the customer is loading, not an empty address book

/tmp/seedco-score/dashboard/src/customers/components/CustomerAddresses/CustomerAddresses.test.tsx

```text
TestingLibraryElementError: Unable to find an element by: [data-test-id="customer-addresses-loading"]

Ignored nodes: comments, script, style
<body>
  <div>
    <main
      id="macaw-ui-root"
    >
      <div
        class="_18fs8ps3 _18fs8psu _18fs8pse6 _18fs8ps3p9"
        data-test-id="customer-addresses"
      >
        <div
          class="_18fs8ps2al _18fs8ps2k9 _18fs8ps2tx _18fs8ps3 _18fs8psr _18fs8ps13 _18fs8ps20"
        >
          <span
            class="_1ruekcr2 _1ruekcr5 _18fs8psuo _18fs8psx6 _18fs8pszo _18fs8ps126 _18fs8ps3dx _18fs8ps1jo _18fs8ps1nx _18fs8ps1l6 _18fs8ps20c"
            data-macaw-ui-component="Text"
            style="width: auto;"
          >
            Address Information
          </span>
          <div
            class="_18fs8ps3 _18fs8psr _18fs8psdx"
          >
            <a
              href="/customers/1/addresses"
            >
              <button
                class="_18fs8ps2rx _18fs8ps31l _18fs8ps28l _18fs8ps2i9 _18fs8ps13 _18fs8ps1o _18fs8ps1nc _18fs8ps3 _18fs8ps3zl _18fs8ps20f _18fs8ps3tl _18fs8ps3u3 _18fs8ps1mf _18fs8ps1ml _18fs8ps1m3 _18fs8ps1m9 _18fs8ps3kx _18fs8ps3lm _18fs8ps3ld _18fs8ps3m2 _18fs8ps3jf _18fs8ps3cl _18fs8ps3er _18fs8ps3v9 _18fs8ps3vm _18fs8ps3vd _18fs8ps3wq _18fs8ps3wr _18fs8ps25l _18fs8ps229 _18fs8ps22y _18fs8ps22p _18fs8ps23e _18fs8ps23r _1tm59qwh _18fs8ps29l _18fs8ps2j9 _18fs8ps2s9 _18fs8ps31x _18fs8ps1go _18fs8ps1fr _18fs8ps1ii _18fs8ps1hl _18fs8ps17x _18fs8ps1jc _18fs8ps1ku _18fs8ps1nl _18fs8psdu"
                data-macaw-ui-component="Button"
                data-test-id="manage-addresses"
 
```

### Dashboard: useProductInitialAPIState - Reference Attributes Logic PAGE reference attribute should fetch attribute definition first, then fetch page choices based on entity type

/tmp/seedco-score/dashboard/src/components/ConditionalFilter/API/initialState/product/useProductInitialAPIState.test.tsx

```text
Error: expect(jest.fn()).toHaveBeenNthCalledWith(n, ...expected)

n: 1
Expected: ObjectContaining {"variables": ObjectContaining {"attributesSlugs": ["page-ref-attr"], "choicesFirst": 1, "choicesIds": [], "first": 1}}
Received
->     1: {"query": {"definitions": [{"directives": [], "kind": "OperationDefinition", "name": {"kind": "Name", "value": "_SearchAttributeOperands"}, "operation": "query", "selectionSet": {"kind": "SelectionSet", "selections": [{"alias": undefined, "arguments": [{"kind": "Argument", "name": {"kind": "Name", "value": "first"}, "value": {"kind": "Variable", "name": [Object]}}, {"kind": "Argument", "name": {"kind": "Name", "value": "filter"}, "value": {"fields": [Array], "kind": "ObjectValue"}}], "directives": [], "kind": "Field", "name": {"kind": "Name", "value": "attributes"}, "selectionSet": {"kind": "SelectionSet", "selections": [{"alias": undefined, "arguments": [Array], "directives": [Array], "kind": "Field", "name": [Object], "selectionSet": [Object]}]}}]}, "variableDefinitions": [{"defaultValue": undefined, "directives": [], "kind": "VariableDefinition", "type": {"kind": "ListType", "type": {"kind": "NonNullType", "type": {"kind": "NamedType", "name": {"kind": "Name", "value": "String"}}}}, "variable": {"kind": "Variable", "name": {"kind": "Name", "value": "attributesSlugs"}}}, {"defaultValue": undefined, "directives": [], "kind": "VariableDefinition", "type": {"kind": "ListType", "type": {"kind": "NonNullType", "type": {"kind": "NamedType", "name": {"kind": "Name", "value": "ID"}}}}, "variable": {"kind": "Variable", "name": {"kind": "Name", "val
```

### Dashboard: useProductInitialAPIState - Reference Attributes Logic CATEGORY reference attribute should fetch attribute definition first, then fetch category choices based on entity type

/tmp/seedco-score/dashboard/src/components/ConditionalFilter/API/initialState/product/useProductInitialAPIState.test.tsx

```text
Error: expect(jest.fn()).toHaveBeenNthCalledWith(n, ...expected)

n: 1
Expected: ObjectContaining {"variables": ObjectContaining {"attributesSlugs": ["category-ref-attr"], "choicesFirst": 1, "choicesIds": [], "first": 1}}
Received
->     1: {"query": {"definitions": [{"directives": [], "kind": "OperationDefinition", "name": {"kind": "Name", "value": "_SearchAttributeOperands"}, "operation": "query", "selectionSet": {"kind": "SelectionSet", "selections": [{"alias": undefined, "arguments": [{"kind": "Argument", "name": {"kind": "Name", "value": "first"}, "value": {"kind": "Variable", "name": [Object]}}, {"kind": "Argument", "name": {"kind": "Name", "value": "filter"}, "value": {"fields": [Array], "kind": "ObjectValue"}}], "directives": [], "kind": "Field", "name": {"kind": "Name", "value": "attributes"}, "selectionSet": {"kind": "SelectionSet", "selections": [{"alias": undefined, "arguments": [Array], "directives": [Array], "kind": "Field", "name": [Object], "selectionSet": [Object]}]}}]}, "variableDefinitions": [{"defaultValue": undefined, "directives": [], "kind": "VariableDefinition", "type": {"kind": "ListType", "type": {"kind": "NonNullType", "type": {"kind": "NamedType", "name": {"kind": "Name", "value": "String"}}}}, "variable": {"kind": "Variable", "name": {"kind": "Name", "value": "attributesSlugs"}}}, {"defaultValue": undefined, "directives": [], "kind": "VariableDefinition", "type": {"kind": "ListType", "type": {"kind": "NonNullType", "type": {"kind": "NamedType", "name": {"kind": "Name", "value": "ID"}}}}, "variable": {"kind": "Variable", "name": {"kind": "Name", 
```

### Dashboard: useProductInitialAPIState - Reference Attributes Logic COLLECTION reference attribute should fetch attribute definition first, then fetch collection choices based on entity type

/tmp/seedco-score/dashboard/src/components/ConditionalFilter/API/initialState/product/useProductInitialAPIState.test.tsx

```text
Error: expect(jest.fn()).toHaveBeenNthCalledWith(n, ...expected)

n: 1
Expected: ObjectContaining {"variables": ObjectContaining {"attributesSlugs": ["collection-ref-attr"], "choicesFirst": 1, "choicesIds": [], "first": 1}}
Received
->     1: {"query": {"definitions": [{"directives": [], "kind": "OperationDefinition", "name": {"kind": "Name", "value": "_SearchAttributeOperands"}, "operation": "query", "selectionSet": {"kind": "SelectionSet", "selections": [{"alias": undefined, "arguments": [{"kind": "Argument", "name": {"kind": "Name", "value": "first"}, "value": {"kind": "Variable", "name": [Object]}}, {"kind": "Argument", "name": {"kind": "Name", "value": "filter"}, "value": {"fields": [Array], "kind": "ObjectValue"}}], "directives": [], "kind": "Field", "name": {"kind": "Name", "value": "attributes"}, "selectionSet": {"kind": "SelectionSet", "selections": [{"alias": undefined, "arguments": [Array], "directives": [Array], "kind": "Field", "name": [Object], "selectionSet": [Object]}]}}]}, "variableDefinitions": [{"defaultValue": undefined, "directives": [], "kind": "VariableDefinition", "type": {"kind": "ListType", "type": {"kind": "NonNullType", "type": {"kind": "NamedType", "name": {"kind": "Name", "value": "String"}}}}, "variable": {"kind": "Variable", "name": {"kind": "Name", "value": "attributesSlugs"}}}, {"defaultValue": undefined, "directives": [], "kind": "VariableDefinition", "type": {"kind": "ListType", "type": {"kind": "NonNullType", "type": {"kind": "NamedType", "name": {"kind": "Name", "value": "ID"}}}}, "variable": {"kind": "Variable", "name": {"kind": "Name"
```

### Dashboard: TokenArray / fetchingParams / toCustomerFetchingParams should return fetching params

/tmp/seedco-score/dashboard/src/components/ConditionalFilter/ValueProvider/TokenArray/fetchingParams.test.ts

```text
TypeError: c.isAttribute is not a function

```

### Dashboard: CustomerAttributesCard links the type chip next to Attributes to the customer type page

/tmp/seedco-score/dashboard/src/customers/components/CustomerAttributesCard/CustomerAttributesCard.test.tsx

```text
Error: expect(received).toHaveAttribute()

received value must be an HTMLElement or an SVGElement.
Received has value: null

```

### Dashboard: CustomerAttributesCard hides View type without customer-type permissions

/tmp/seedco-score/dashboard/src/customers/components/CustomerAttributesCard/CustomerAttributesCard.test.tsx

```text
Error: expect(element).not.toBeInTheDocument()

expected document not to contain element, found <a data-test-id="view-customer-type" href="/customer-types/type-1"><span class="_1ruekcr2 _1ruekcr5 _18fs8psuo _18fs8psx6 _18fs8pszo _18fs8ps126 _18fs8ps3b9 _18fs8ps1jc _18fs8ps1nl _18fs8ps1ku _18fs8ps209" data-macaw-ui-component="Text">Type settings</span></a> instead

```

### Dashboard: CustomerAttributesCard applies a revert to the saved type without confirmation

/tmp/seedco-score/dashboard/src/customers/components/CustomerAttributesCard/CustomerAttributesCard.test.tsx

```text
TestingLibraryElementError: Unable to find an element by: [data-test-id="customer-type-option-type-1"]

Ignored nodes: comments, script, style
<body
  style=""
>
  <div>
    <main
      id="macaw-ui-root"
    >
      <div
        class="_18fs8ps3 _18fs8psu _18fs8pse6 _18fs8ps3p9"
        data-test-id="customer-attributes"
      >
        <div
          class="_18fs8ps2al _18fs8ps2k9 _18fs8ps2tx _18fs8ps3 _18fs8psr _18fs8ps13 _18fs8ps20"
        >
          <span
            class="_1ruekcr2 _1ruekcr5 _18fs8psuo _18fs8psx6 _18fs8pszo _18fs8ps126 _18fs8ps3dx _18fs8ps1jo _18fs8ps1nx _18fs8ps1l6 _18fs8ps20c"
            data-macaw-ui-component="Text"
            style="width: auto;"
          >
            Attributes
          </span>
          <div
            class="_18fs8ps3 _18fs8psr _18fs8psdx"
          >
            <div
              class="_18fs8ps3 _18fs8ps13 _18fs8psdx"
              data-test-id="customer-attributes-menu"
            >
              <span
                class="_1ruekcr2 _1ruekcr5 _18fs8psuo _18fs8psx6 _18fs8pszo _18fs8ps126 _18fs8ps3e9 _18fs8ps1jc _18fs8ps1nl _18fs8ps1ku _18fs8ps209"
                data-macaw-ui-component="Text"
                data-test-id="customer-attributes-type"
              >
                Wholesale
              </span>
              <button
                class="_18fs8ps2rx _18fs8ps31l _18fs8ps28l _18fs8ps2i9 _18fs8ps13 _18fs8ps1o _18fs8ps1nc _18fs8ps3 _18fs8ps3zl _18fs8ps20f _18fs8ps3tl _18fs8ps3u3 _18fs8ps1mf _18fs8ps1ml _18fs8ps1m3 _18fs8ps1m9 _18fs8ps3kx _18fs8ps3lm _18fs8ps3ld _18fs8ps3m2 _18fs8ps3jf _18fs8ps3cl _
```

### Dashboard: CustomerAttributesCard hides Change type for read-only users

/tmp/seedco-score/dashboard/src/customers/components/CustomerAttributesCard/CustomerAttributesCard.test.tsx

```text
Error: expect(element).not.toBeInTheDocument()

expected document not to contain element, found <div class="_18fs8ps3 _18fs8ps13 _18fs8psdx" data-test-id="customer-attributes-menu"><span class="_1ruekcr2 _1ruekcr5 _18fs8psuo _18fs8psx6 _18fs8pszo _18fs8ps126 _18fs8ps3e9 _18fs8ps1jc _18fs8ps1nl _18fs8ps1ku _18fs8ps209" data-macaw-ui-component="Text" data-test-id="customer-attributes-type">Default</span><button class="_18fs8ps2rx _18fs8ps31l _18fs8ps28l _18fs8ps2i9 _18fs8ps13 _18fs8ps1o _18fs8ps1nc _18fs8ps3 _18fs8ps3zl _18fs8ps20f _18fs8ps3tl _18fs8ps3u3 _18fs8ps1mf _18fs8ps1ml _18fs8ps1m3 _18fs8ps1m9 _18fs8ps3kx _18fs8ps3lm _18fs8ps3ld _18fs8ps3m2 _18fs8ps3jf _18fs8ps3cl _18fs8ps3er _18fs8ps3v9 _18fs8ps3vm _18fs8ps3vd _18fs8ps3wq _18fs8ps3wr _18fs8ps25l _18fs8ps229 _18fs8ps22y _18fs8ps22p _18fs8ps23e _18fs8ps23r _1tm59qwg _18fs8ps299 _18fs8ps2ix _18fs8ps2rx _18fs8ps31l _18fs8ps1gl _18fs8ps1fo _18fs8ps1if _18fs8ps1hi _18fs8ps17r _18fs8ps1j9 _18fs8ps1kr _18fs8ps1ni _18fs8psdu" data-macaw-ui-component="Button" data-test-id="change-customer-type" disabled="" type="button">Change type</button><a data-test-id="view-customer-type" href="/customer-types/type-1"><span class="_1ruekcr2 _1ruekcr5 _18fs8psuo _18fs8psx6 _18fs8pszo _18fs8ps126 _18fs8ps3b9 _18fs8ps1jc _18fs8ps1nl _18fs8ps1ku _18fs8ps209" data-macaw-ui-component="Text">Type settings</span></a></div> instead

```

### Dashboard suite did not load

/tmp/seedco-score/dashboard/src/components/Sidebar/menu/createCustomerTypeMenuItems.test.ts

  ● Test suite failed to run

    Cannot find module './createCustomerTypeMenuItems' from 'src/components/Sidebar/menu/createCustomerTypeMenuItems.test.ts'

    However, Jest was able to find:
    	'./createCustomerTypeMenuItems.test.ts'

    You might want to include a file extension in your import, or update your 'moduleFileExtensions', which is currently ['ts', 'tsx', 'js', 'jsx', 'json', 'node'].

    See https://jestjs.io/docs/configuration#modulefileextensions-arraystring

       5 |   createCustomerTypeMenuItems,
       6 |   CUSTOMER_TYPE_NAV_ALL_ID,
    >  7 |   CUSTOMER_TYPE_NAV_ID_PREFIX,
         |                                      ^
       8 |   getCustomerTypeIdsFromSearch,
       9 |   isCustomerTypeNavItem,
      10 |   MAX_CUSTOMER_TYPE_NAV_TYPES,

  

### Dashboard: CustomerListPage create CTA shows a simple Create customer button when the user cannot manage types

/tmp/seedco-score/dashboard/src/customers/components/CustomerListPage/CustomerListPage.test.tsx

```text
Error: expect(element).not.toBeInTheDocument()

expected document not to contain element, found <button aria-expanded="false" aria-haspopup="menu" class="_18fs8ps2rx _18fs8ps31l _18fs8ps28l _18fs8ps2i9 _18fs8ps13 _18fs8ps1o _18fs8ps1nc _18fs8ps3 _18fs8ps3zl _18fs8ps20f _18fs8ps3tl _18fs8ps3u3 _18fs8ps3jl _18fs8ps3ka _18fs8ps3k1 _18fs8ps3kq _18fs8ps3jf _18fs8ps3c9 _18fs8ps3er _18fs8ps3v9 _18fs8ps3vm _18fs8ps3vd _18fs8ps3wq _18fs8ps3wr _18fs8ps259 _1tm59qwh _1tm59qwj _18fs8ps2s9 _18fs8ps31x _18fs8ps28x _18fs8ps2il _18fs8ps1go _18fs8ps1fr _18fs8ps1ii _18fs8ps1hl _18fs8ps17x _18fs8ps15c _18fs8ps1jc _18fs8ps1ku _18fs8ps1nl _18fs8psdu segment" data-macaw-ui-component="Dropdown.Trigger" data-state="closed" data-test-id="create-customer-dropdown" id="radix-:r7:" type="button"><svg aria-hidden="true" class="lucide lucide-chevron-down" fill="none" height="20" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" viewBox="0 0 24 24" width="20" xmlns="http://www.w3.org/2000/svg"><path d="m6 9 6 6 6-6" /></svg></button> instead

```

### Dashboard: resolveAttributeComboboxOptions keeps API options when the selected slug is already present

/tmp/seedco-score/dashboard/src/components/ConditionalFilter/UI/resolveAttributeComboboxState.test.ts

```text
Error: expect(received).toEqual(expected) // deep equality

- Expected  - 0
+ Received  + 5

@@ -1,8 +1,13 @@
  Array [
    Object {
      "label": "Tier",
+     "type": "DROPDOWN",
+     "value": "tier",
+   },
+   Object {
+     "label": "Tier",
      "slug": "tier",
      "type": "DROPDOWN",
      "value": "QXR0cmlidXRlOjE=",
    },
    Object {

```

### Dashboard: resolveAttributeComboboxOptions prepends the selected attribute when the fetched list does not include it

/tmp/seedco-score/dashboard/src/components/ConditionalFilter/UI/resolveAttributeComboboxState.test.ts

```text
Error: expect(received).toEqual(expected) // deep equality

- Expected  - 1
+ Received  + 0

@@ -1,9 +1,8 @@
  Array [
    Object {
      "label": "Tier",
-     "slug": "tier",
      "type": "DROPDOWN",
      "value": "tier",
    },
    Object {
      "label": "Contract date",

```

### Dashboard: resolveAttributeComboboxValue uses the fetched option so the combobox value matches the list identity

/tmp/seedco-score/dashboard/src/components/ConditionalFilter/UI/resolveAttributeComboboxState.test.ts

```text
Error: expect(received).toEqual(expected) // deep equality

- Expected  - 2
+ Received  + 1

  Object {
    "label": "Tier",
-   "slug": "tier",
    "type": "DROPDOWN",
-   "value": "QXR0cmlidXRlOjE=",
+   "value": "tier",
  }

```

### Dashboard: resolveAttributeComboboxValue falls back to the selected slug when the list has not loaded yet

/tmp/seedco-score/dashboard/src/components/ConditionalFilter/UI/resolveAttributeComboboxState.test.ts

```text
Error: expect(received).toEqual(expected) // deep equality

- Expected  - 1
+ Received  + 0

  Object {
    "label": "Tier",
-   "slug": "tier",
    "type": "DROPDOWN",
    "value": "tier",
  }

```

### Dashboard: CustomerDetailsPage with MANAGE_USERS (full edit access) renders the savebar (cancel/save buttons)

/tmp/seedco-score/dashboard/src/customers/components/CustomerDetailsPage/CustomerDetailsPage.test.tsx

```text
Error: expect(element).not.toBeInTheDocument()

expected document not to contain element, found <button>delete</button> instead

```

### Dashboard: CustomerDetailsPage with only MANAGE_ORDERS (read-only access) hides the metadata edit button

/tmp/seedco-score/dashboard/src/customers/components/CustomerDetailsPage/CustomerDetailsPage.test.tsx

```text
Error: Element type is invalid: expected a string (for built-in components) or a class/function (for composite components) but got: object.

Check the render method of `Form`.

```

### Dashboard: CustomerDetailsPage with only MANAGE_ORDERS (read-only access) still shows the cogs menu for the built-in Open in GraphiQL action

/tmp/seedco-score/dashboard/src/customers/components/CustomerDetailsPage/CustomerDetailsPage.test.tsx

```text
Error: Element type is invalid: expected a string (for built-in components) or a class/function (for composite components) but got: object.

Check the render method of `Form`.

```

### Dashboard: CustomerDetailsPage with only MANAGE_ORDERS (read-only access) hides the savebar action buttons (no delete/cancel/save)

/tmp/seedco-score/dashboard/src/customers/components/CustomerDetailsPage/CustomerDetailsPage.test.tsx

```text
Error: Element type is invalid: expected a string (for built-in components) or a class/function (for composite components) but got: object.

Check the render method of `Form`.

```

### Dashboard: CustomerDetailsPage with only MANAGE_ORDERS (read-only access) shows the read-only label in the savebar slot

/tmp/seedco-score/dashboard/src/customers/components/CustomerDetailsPage/CustomerDetailsPage.test.tsx

```text
Error: Element type is invalid: expected a string (for built-in components) or a class/function (for composite components) but got: object.

Check the render method of `Form`.

```

### Dashboard: CustomerDetailsPage with only MANAGE_ORDERS (read-only access) disables customer form fields

/tmp/seedco-score/dashboard/src/customers/components/CustomerDetailsPage/CustomerDetailsPage.test.tsx

```text
Error: Element type is invalid: expected a string (for built-in components) or a class/function (for composite components) but got: object.

Check the render method of `Form`.

```

### Dashboard: CustomerDetailsPage with only MANAGE_ORDERS (read-only access) disables customer type changes on the attributes card

/tmp/seedco-score/dashboard/src/customers/components/CustomerDetailsPage/CustomerDetailsPage.test.tsx

```text
Error: Element type is invalid: expected a string (for built-in components) or a class/function (for composite components) but got: object.

Check the render method of `Form`.

```

### Dashboard: CustomerDetailsPage with only MANAGE_STAFF (read-only access) disables customer form fields

/tmp/seedco-score/dashboard/src/customers/components/CustomerDetailsPage/CustomerDetailsPage.test.tsx

```text
Error: expect(element).toBeDisabled()

Received element is not disabled:
  <div class="MuiFormControl-root MuiTextField-root MuiFormControl-fullWidth" data-test-id="customer-first-name" />

```

### Dashboard: CustomerDetailsPage read-only with extension menu items still surfaces the cogs menu so extension actions remain reachable

/tmp/seedco-score/dashboard/src/customers/components/CustomerDetailsPage/CustomerDetailsPage.test.tsx

```text
Error: Element type is invalid: expected a string (for built-in components) or a class/function (for composite components) but got: object.

Check the render method of `Form`.

```

### Dashboard: WarehouseHandler fetches warehouses with correct query and variables

/tmp/seedco-score/dashboard/src/components/ConditionalFilter/API/Handler.test.ts

```text
Error: expect(jest.fn()).toHaveBeenCalledWith(...expected)

- Expected
+ Received

@@ -186,10 +186,9 @@
        "end": 207,
        "start": 0,
      },
    },
    "variables": Object {
-     "after": undefined,
-     "first": 20,
+     "first": 5,
      "query": "main",
    },
  },

Number of calls: 1

```

### Dashboard: WarehouseHandler requests the next page when after is provided

/tmp/seedco-score/dashboard/src/components/ConditionalFilter/API/Handler.test.ts

```text
Error: expect(jest.fn()).toHaveBeenCalledWith(...expected)

- Expected
+ Received

@@ -186,10 +186,9 @@
        "end": 207,
        "start": 0,
      },
    },
    "variables": Object {
-     "after": "cursor-1",
-     "first": 20,
+     "first": 5,
      "query": "main",
    },
  },

Number of calls: 1

```

### Dashboard: WarehouseHandler handles empty search query

/tmp/seedco-score/dashboard/src/components/ConditionalFilter/API/Handler.test.ts

```text
Error: expect(jest.fn()).toHaveBeenCalledWith(...expected)

- Expected
+ Received

@@ -186,10 +186,9 @@
        "end": 207,
        "start": 0,
      },
    },
    "variables": Object {
-     "after": undefined,
-     "first": 20,
+     "first": 5,
      "query": "",
    },
  },

Number of calls: 1

```

### Dashboard: CustomerTypeDetailsPage top nav hides set as default and delete on the default customer type

/tmp/seedco-score/dashboard/src/customerTypes/components/CustomerTypeDetailsPage/CustomerTypeDetailsPage.topNav.test.tsx

```text
Error: expect(element).not.toBeInTheDocument()

expected document not to contain element, found <li aria-disabled="true" class="_6vehm82 _18fs8ps2sl _18fs8ps329 _18fs8ps1gr _18fs8ps1fu _18fs8ps1il _18fs8ps1ho _18fs8ps3 _18fs8ps13 _18fs8ps3tl _18fs8ps3u3 _18fs8ps3sl _18fs8ps3qe _18fs8ps3py _18fs8ps3pn _18fs8ps299 _18fs8ps2qx" data-macaw-ui-component="Dropdown.Item" data-orientation="vertical" data-radix-collection-item="" data-test-id="delete-customer-type" role="menuitem" style="cursor: not-allowed; opacity: 0.5; pointer-events: none;" tabindex="-1"><div class="_18fs8ps3 _18fs8ps13 _18fs8psdx"><div class="_18fs8ps3d9" style="align-items: center; display: inline-flex; flex-shrink: 0; height: 16px; justify-content: center; line-height: 0; width: 16px;"><svg aria-hidden="true" class="lucide lucide-trash2 lucide-trash-2" fill="none" height="16" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" viewBox="0 0 24 24" width="16" xmlns="http://www.w3.org/2000/svg"><path d="M10 11v6" /><path d="M14 11v6" /><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6" /><path d="M3 6h18" /><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" /></svg></div><span class="_1ruekcr2 _1ruekcr5 _18fs8psuo _18fs8psx6 _18fs8pszo _18fs8ps126 _18fs8ps3d9 _18fs8ps1ji _18fs8ps1nr _18fs8ps1l0 _18fs8ps209" data-macaw-ui-component="Text">Delete customer type</span></div></li> instead

```

### Dashboard: ConditionalFilter / FilterElement / Condition creates instance from url token

/tmp/seedco-score/dashboard/src/components/ConditionalFilter/FilterElement/Condition.test.ts

```text
Error: expect(received).toEqual(expected) // deep equality

- Expected  - 10
+ Received  +  4

@@ -1,8 +1,8 @@
- Object {
+ Condition {
    "loading": false,
-   "options": Array [
+   "options": ConditionOptions [
      Object {
        "label": "is",
        "type": "combobox",
        "value": "input-1",
      },
@@ -10,24 +10,18 @@
        "label": "in",
        "type": "multiselect",
        "value": "input-2",
      },
    ],
-   "selected": Object {
+   "selected": ConditionSelected {
      "conditionValue": Object {
        "label": "is",
        "type": "combobox",
        "value": "input-1",
      },
      "loading": false,
-     "options": Array [
-       Object {
-         "label": "Cat1",
-         "slug": "cat1",
-         "value": "cat-1-id",
-       },
-     ],
+     "options": Array [],
      "value": Object {
        "label": "Cat1",
        "slug": "cat1",
        "value": "cat-1-id",
      },

```

### Dashboard: ConditionalFilter / FilterElement / Condition creates instance from url token

/tmp/seedco-score/dashboard/src/components/ConditionalFilter/FilterElement/Condition.test.ts

```text
Error: expect(received).toEqual(expected) // deep equality

- Expected  - 11
+ Received  +  4

@@ -1,29 +1,22 @@
- Object {
+ Condition {
    "loading": false,
-   "options": Array [
+   "options": ConditionOptions [
      Object {
        "label": "in",
        "type": "multiselect",
        "value": "input-2",
      },
    ],
-   "selected": Object {
+   "selected": ConditionSelected {
      "conditionValue": Object {
        "label": "in",
        "type": "multiselect",
        "value": "input-2",
      },
      "loading": false,
-     "options": Array [
-       Object {
-         "label": "Some attr 1z",
-         "originalSlug": "some-attr-1z",
-         "slug": "some-attr-1z",
-         "value": "some-attr-1z",
-       },
-     ],
+     "options": Array [],
      "value": Array [
        Object {
          "label": "Some attr 1z",
          "originalSlug": "some-attr-1z",
          "slug": "some-attr-1z",

```

### Dashboard: ConditionalFilter / queryVariables / createCustomerWhereVariables should create variables with selected filters

/tmp/seedco-score/dashboard/src/components/ConditionalFilter/queryVariables.test.ts

```text
Error: expect(received).toEqual(expected) // deep equality

- Expected  - 6
+ Received  + 1

@@ -6,22 +6,17 @@
          "value": Object {
            "eq": "m-value",
          },
        },
      },
-     Object {
+   ],
    "dateJoined": Object {
      "gte": "2025-02-01T00:00:00.000Z",
      "lte": "2025-02-08T00:00:00.000Z",
-       },
    },
-     Object {
    "numberOfOrders": Object {
      "range": Object {
        "gte": 1,
        "lte": 100,
      },
    },
-     },
-   ],
-   "OR": undefined,
  }

```

### Dashboard: ConditionalFilter / queryVariables / createCustomerWhereVariables should keep customerType alongside the other customer filters

/tmp/seedco-score/dashboard/src/components/ConditionalFilter/queryVariables.test.ts

```text
Error: expect(received).toEqual(expected) // deep equality

- Expected  - 7
+ Received  + 0

  Object {
-   "AND": Array [
-     Object {
    "customerType": Object {
      "eq": "id-1",
-       },
    },
-     Object {
    "dateJoined": Object {
      "gte": "2025-02-01T00:00:00.000Z",
      "lte": "2025-02-08T00:00:00.000Z",
    },
-     },
-   ],
-   "OR": undefined,
  }

```

### Dashboard: ConditionalFilter / queryVariables / createCustomerWhereVariables should put customer attributes on where as AssignedAttributeWhereInput

/tmp/seedco-score/dashboard/src/components/ConditionalFilter/queryVariables.test.ts

```text
Error: expect(received).toEqual(expected) // deep equality

- Expected  - 5
+ Received  + 0

  Object {
-   "AND": Array [
-     Object {
    "attributes": Array [
      Object {
        "slug": "industry",
        "value": Object {
          "slug": Object {
            "eq": "retail",
          },
        },
      },
    ],
-     },
-   ],
-   "OR": undefined,
  }

```

### Dashboard: ConditionalFilter / queryVariables / createCustomerWhereVariables should put customerType on where using entity IDs

/tmp/seedco-score/dashboard/src/components/ConditionalFilter/queryVariables.test.ts

```text
Error: expect(received).toEqual(expected) // deep equality

- Expected  - 5
+ Received  + 0

  Object {
-   "AND": Array [
-     Object {
    "customerType": Object {
      "eq": "id-1",
    },
-     },
-   ],
-   "OR": undefined,
  }

```

### Dashboard: mapAssignedAttribute maps multi-choice slugs

/tmp/seedco-score/dashboard/src/customers/utils/customerAttributes.test.ts

```text
Error: expect(received).toEqual(expected) // deep equality

- Expected  - 4
+ Received  + 1

- Array [
-   "a",
-   "b",
- ]
+ Array []

```

### Dashboard: getAttributeInputFromCustomerType restores assigned values when a shared previous field is empty

/tmp/seedco-score/dashboard/src/customers/utils/customerAttributes.test.ts

```text
Error: expect(received).toEqual(expected) // deep equality

- Expected  - 3
+ Received  + 1

- Array [
-   "gold",
- ]
+ Array []

```

### Dashboard: hydrateChoiceCount asks for every selected id, and at least one when the list is empty

/tmp/seedco-score/dashboard/src/components/ConditionalFilter/API/filterChoicesPage.test.ts

```text
Error: expect(received).toBe(expected) // Object.is equality

Expected: 3
Received: 20

```

### Dashboard: CustomerDetailsTitle renders customer name and linked customer type when loaded

/tmp/seedco-score/dashboard/src/customers/components/CustomerDetailsPage/Title.test.tsx

```text
TestingLibraryElementError: Unable to find an element by: [data-test-id="account-status-active"]

Ignored nodes: comments, script, style
<body>
  <div>
    <main
      id="macaw-ui-root"
    >
      <div
        class="_18fs8ps3 _18fs8ps13 _18fs8psdx _18fs8psdo"
      >
        <span>
          Tom Cooper
        </span>
        <div
          class="MuiChip-root Pill-pill-15 Pill-root-16 Pill-info-26"
          data-test-id="customer-details-status-active"
          style="background-color: rgb(217, 246, 202); border-color: #bfdbb1; color: rgb(55, 76, 43); font-weight: 500;"
        >
          <span
            class="MuiChip-label Pill-label-27"
          >
            Active
          </span>
        </div>
        <a
          aria-label="View customers of B2B"
          class="link"
          href="/customers/?customerTypes%5B0%5D=Q3VzdG9tZXJUeXBlOjE%3D"
          title="View customers of B2B"
        >
          <span
            aria-label="Customer type: B2B"
            class="_1ruekcr2 _1ruekcr5 _18fs8psuo _18fs8psx6 _18fs8pszo _18fs8ps126 _18fs8ps3e9 _18fs8ps1jc _18fs8ps1nl _18fs8ps1ku _18fs8ps20c _18fs8ps3 _18fs8ps13 _18fs8psdu"
            data-macaw-ui-component="Text"
            data-test-id="customer-details-customer-type"
          >
            <div
              aria-hidden="true"
              class="icon"
              style="width: 14px; height: 14px;"
            >
              <svg
                aria-hidden="true"
                class="lucide lucide-users"
                fill="none"
                height="14"
                stroke="currentCo
```

### Dashboard: CustomerDetailsTitle renders Inactive and Unverified pills for a deactivated unconfirmed customer

/tmp/seedco-score/dashboard/src/customers/components/CustomerDetailsPage/Title.test.tsx

```text
TestingLibraryElementError: Unable to find an element by: [data-test-id="account-status-inactive"]

Ignored nodes: comments, script, style
<body>
  <div>
    <main
      id="macaw-ui-root"
    >
      <div
        class="_18fs8ps3 _18fs8ps13 _18fs8psdx _18fs8psdo"
      >
        <span>
          Tom Cooper
        </span>
        <div
          class="MuiChip-root Pill-pill-29 Pill-root-30 Pill-info-40"
          data-test-id="customer-details-status-inactive"
          style="background-color: rgba(245, 245, 245, 0.302); border-color: #6969694d; color: rgb(77, 77, 77); font-weight: 500;"
        >
          <span
            class="MuiChip-label Pill-label-41"
          >
            Inactive
          </span>
        </div>
        <a
          aria-label="View customers of B2B"
          class="link"
          href="/customers/?customerTypes%5B0%5D=Q3VzdG9tZXJUeXBlOjE%3D"
          title="View customers of B2B"
        >
          <span
            aria-label="Customer type: B2B"
            class="_1ruekcr2 _1ruekcr5 _18fs8psuo _18fs8psx6 _18fs8pszo _18fs8ps126 _18fs8ps3e9 _18fs8ps1jc _18fs8ps1nl _18fs8ps1ku _18fs8ps20c _18fs8ps3 _18fs8ps13 _18fs8psdu"
            data-macaw-ui-component="Text"
            data-test-id="customer-details-customer-type"
          >
            <div
              aria-hidden="true"
              class="icon"
              style="width: 14px; height: 14px;"
            >
              <svg
                aria-hidden="true"
                class="lucide lucide-users"
                fill="none"
                height="14"
                s
```

### Dashboard: createConfigurationMenu orders groups by merchant job and drops legacy labels

/tmp/seedco-score/dashboard/src/configuration/createConfigurationMenu.test.ts

```text
Error: expect(received).toEqual(expected) // deep equality

- Expected  - 1
+ Received  + 1

  Array [
    "Store",
    "Markets & channels",
    "Products & catalog",
    "Content",
+   "Customers",
    "Shipping & delivery",
    "Orders",
-   "Customers",
    "Users & permissions",
  ]

```

### Dashboard: CustomerOrders renders order number, fulfillment status, total, and channel for support jump-list jobs

/tmp/seedco-score/dashboard/src/customers/components/CustomerOrders/CustomerOrders.test.tsx

```text
Error: Element type is invalid: expected a string (for built-in components) or a class/function (for composite components) but got: undefined. You likely forgot to export your component from the file it's defined in, or you might have mixed up default and named imports.

```

### Dashboard: CustomerOrders renders an empty state when the customer has no orders

/tmp/seedco-score/dashboard/src/customers/components/CustomerOrders/CustomerOrders.test.tsx

```text
Error: Element type is invalid: expected a string (for built-in components) or a class/function (for composite components) but got: undefined. You likely forgot to export your component from the file it's defined in, or you might have mixed up default and named imports.

```

### Dashboard: CustomerOrders keeps View all disabled and unlinked while orders are loading

/tmp/seedco-score/dashboard/src/customers/components/CustomerOrders/CustomerOrders.test.tsx

```text
Error: Element type is invalid: expected a string (for built-in components) or a class/function (for composite components) but got: undefined. You likely forgot to export your component from the file it's defined in, or you might have mixed up default and named imports.

```


Source trial: /Users/lilinwang/Documents/projects/SWE-Pod/runs/harbor/company-cc-team-fable-5-2-v1/customer_attributes_company_team__JNaUPSL
