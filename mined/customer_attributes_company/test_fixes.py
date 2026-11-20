"""Fixes to upstream's hidden tests, applied when the task is exported (tools/export_harbor_company.py).

Each one changes how a test checks, never what it checks: a test that failed a correct alternative for a reason the
brief and INTERFACE.md do not settle is made to accept it, and the behaviour it was written for is still required.
The reference (upstream's own code) passes every fixed test, as before; the validation run checks that.

Found by a review of the Fable 5.2 team run (company-cc-team-fable-5-2-v1). Tests that check presentation alone
(where a button sits, in what order groups are listed) are not changed here: the rubric moves them to a measure.
"""

FIXES = [
    {
        "owner": "dashboard",
        "file": "src/customers/components/CustomerDetailsPage/CustomerDetailsPage.test.tsx",
        "why": "The stand-in for the orders card gave only the named export. A page that imports the component the "
               "way the page does today (the default export, through the folder) rendered an empty object and every "
               "test of the page crashed: one missing export cost seven tests of permissions. The stand-in now gives "
               "both; the named export is still required, by CustomerOrders' own tests.",
        "old": '''jest.mock("../CustomerOrders/CustomerOrders", () => ({
  CustomerOrders: () => <div data-test-id="customer-orders-mock" />,
}));''',
        "new": '''jest.mock("../CustomerOrders/CustomerOrders", () => {
  const CustomerOrders = () => <div data-test-id="customer-orders-mock" />;

  return { __esModule: true, default: CustomerOrders, CustomerOrders };
});''',
    },
    {
        "owner": "dashboard",
        "file": "src/customers/components/CustomerDetailsPage/CustomerDetailsPage.test.tsx",
        "why": "The helper took the element carrying the test id to be the input itself, as it is with Macaw's input. "
               "With a field whose test id sits on a wrapper, `toBeDisabled` was asked of a div. It now looks at the "
               "input inside: the field must still be disabled.",
        "old": '''const getInputByTestId = (testId: string): HTMLInputElement =>
  screen.getByTestId(testId) as HTMLInputElement;''',
        "new": '''const getInputByTestId = (testId: string): HTMLInputElement => {
  const found = screen.getByTestId(testId);
  const field = "input, textarea, select";

  return (found.matches(field) ? found : (found.querySelector(field) ?? found)) as HTMLInputElement;
};''',
    },
    {
        "owner": "dashboard",
        "file": "src/components/ConditionalFilter/queryVariables.test.ts",
        "why": "The API applies the predicates at the top of a `where` one after another, so `{a, b}` and "
               "`{AND: [{a}, {b}]}` ask for the same customers, and `OR: undefined` is not sent at all. The customer "
               "tests now compare what is asked for: single-level ANDs of distinct fields are merged, and absent "
               "values dropped, on both sides. Every predicate and value must still be there.",
        "old": '''describe("ConditionalFilter / queryVariables / createCustomerWhereVariables", () => {''',
        "new": '''// What a customer `where` asks for: the API applies top-level predicates one after another, so an AND of
// distinct fields is the same as those fields side by side, and a value left undefined is not sent.
const sameWhere = (where: unknown): unknown => {
  if (Array.isArray(where)) {
    return where.map(sameWhere);
  }

  if (!where || typeof where !== "object") {
    return where;
  }

  const out: Record<string, unknown> = {};

  for (const [key, value] of Object.entries(where as Record<string, unknown>)) {
    if (value !== undefined) {
      out[key] = sameWhere(value);
    }
  }

  const and = out.AND;

  if (Array.isArray(and) && and.every(part => part && typeof part === "object" && !Array.isArray(part))) {
    const merged: Record<string, unknown> = { ...out };

    delete merged.AND;

    const keys = and.flatMap(part => Object.keys(part as object));

    if (new Set(keys).size === keys.length && keys.every(key => !(key in merged))) {
      return sameWhere(Object.assign(merged, ...(and as object[])));
    }
  }

  return out;
};
const expectWhere = (result: unknown) => ({
  toEqual: (expected: unknown) => expect(sameWhere(result)).toEqual(sameWhere(expected)),
});

describe("ConditionalFilter / queryVariables / createCustomerWhereVariables", () => {''',
        "within": ['describe("ConditionalFilter / queryVariables / createCustomerWhereVariables"',
                   'describe("ConditionalFilter / queryVariables / createProductTypesQueryVariables"'],
        "then": [("expect(result).toEqual(", "expectWhere(result).toEqual(")],
    },
    {
        "owner": "dashboard",
        "file": "src/components/ConditionalFilter/FiltersQueryBuilder/queryVarsBuilders/AssignedAttributeQueryVarsBuilder.test.ts",
        "why": "The API reads a numeric range's bounds as decimals and accepts \"10\" as it accepts 10. The test now "
               "accepts either; the bounds must still be on value.numeric.range.",
        "old": '''range: { gte: 10, lte: 20 }''',
        "new": '''range: { gte: numberLike(10), lte: numberLike(20) }''',
        "prepend": '''// a bound the API reads as a decimal: 10 and "10" are the same to it
const numberLike = (n: number) => ({
  asymmetricMatch: (value: unknown) => (typeof value === "number" || typeof value === "string") && Number(value) === n,
  toAsymmetricMatcher: () => "numberLike(" + n + ")",
});

''',
    },
    {
        "owner": "dashboard",
        "file": "src/components/ConditionalFilter/FiltersQueryBuilder/queryVarsBuilders/AssignedAttributeQueryVarsBuilder.test.ts",
        "why": "`oneOf` is a set to the API: it matches values in any of the listed ones, whatever their order. The test "
               "failed a filter that listed the same two values the other way round (Fable 5.2 solo v3). The values "
               "must still be exactly those.",
        "old": '''slug: { oneOf: ["vip", "retail"] }''',
        "new": '''slug: { oneOf: sameMembers(["vip", "retail"]) }''',
        "prepend": '''// a list the API reads as a set (`oneOf`): the same members, in any order
const sameMembers = (expected: unknown[]) => ({
  asymmetricMatch: (value: unknown) =>
    Array.isArray(value) &&
    value.length === expected.length &&
    expected.every(item => value.some(v => JSON.stringify(v) === JSON.stringify(item))),
  toAsymmetricMatcher: () => "sameMembers(" + JSON.stringify(expected) + ")",
});

''',
    },
    {
        "owner": "dashboard",
        "file": "src/components/ConditionalFilter/FiltersQueryBuilder/queryVarsBuilders/CustomerTypeQueryVarsBuilder.test.ts",
        "why": "The same: a customer type filter's `oneOf` is a set to the API.",
        "old": '''toEqual({ oneOf: ["id-1", "id-2"] })''',
        "new": '''toEqual({ oneOf: sameMembers(["id-1", "id-2"]) })''',
        "prepend": '''// a list the API reads as a set (`oneOf`): the same members, in any order
const sameMembers = (expected: unknown[]) => ({
  asymmetricMatch: (value: unknown) =>
    Array.isArray(value) &&
    value.length === expected.length &&
    expected.every(item => value.some(v => JSON.stringify(v) === JSON.stringify(item))),
  toAsymmetricMatcher: () => "sameMembers(" + JSON.stringify(expected) + ")",
});

''',
    },
    {
        "owner": "dashboard",
        "file": "src/components/ConditionalFilter/API/Handler.test.ts",
        "why": "How many choices a page of them holds is a choice neither the brief nor INTERFACE.md settles. The "
               "tests now accept any page size; the search text and the cursor of the next page are still checked.",
        "old": '''first: FILTER_CHOICES_PAGE_SIZE,''',
        "new": '''first: expect.any(Number),''',
        "count": 3,
    },
]


def apply(owner, root):
    """Applies this owner's fixes to the tests laid out under `root`. Every fix must apply exactly as written."""
    import os
    done = []
    for fix in (f for f in FIXES if f["owner"] == owner):
        path = os.path.join(root, fix["file"])
        with open(path, encoding="utf-8") as f:
            text = f.read()
        found = text.count(fix["old"])
        assert found == fix.get("count", 1), "{}: expected {} of the text to fix, found {}".format(fix["file"], fix.get("count", 1), found)
        text = text.replace(fix["old"], fix["new"])
        if fix.get("within"):
            start, end = text.index(fix["within"][0]), text.index(fix["within"][1])
            part = text[start:end]
            for old, new in fix.get("then", []):
                assert old in part, (fix["file"], old)
                part = part.replace(old, new)
            text = text[:start] + part + text[end:]
        if fix.get("prepend"):
            lines = text.split("\n")
            last_import = max(i for i, line in enumerate(lines) if line.startswith("import ") or line.startswith("} from "))
            text = "\n".join(lines[:last_import + 1]) + "\n\n" + fix["prepend"].rstrip("\n") + "\n" + "\n".join(lines[last_import + 1:])
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        done.append(fix["file"])
    return done
