Last month the payment provider's key was replaced and nobody told the payment app. Checkout failed for most of a day before anyone noticed: the only trace was in the app's own log. The same thing happened earlier with the mail server's password, and order emails silently stopped. Staff live in the back office, and that is where they need to see such things.

We want apps to be able to report their problems to the shop, and staff to see them in the back office, where the installed apps are listed. It has to work for every app, our partners' included, so it goes through the API. The API below was agreed with the partners and they are building against it, so please build it as written.

```graphql
type App {
  # The app's problems, newest first. For the app itself and for staff who may manage apps.
  problems: [AppProblem!]
}

type AppProblem {
  id: ID!
  key: String!
  message: String!
  count: Int!              # how many times it was reported
  isCritical: Boolean!
  createdAt: DateTime!
  updatedAt: DateTime!
  dismissed: AppProblemDismissed   # null while the problem stands
}

type AppProblemDismissed {
  by: AppProblemDismissedByEnum!   # APP or USER
  userEmail: String                # the staff member, when by is USER
}

input AppProblemCreateInput {
  message: String!            # 3 characters or more
  key: String!                # 3 to 128 characters; names the kind of problem
  criticalThreshold: PositiveInt
  aggregationPeriod: Minute = 60
}

# Only one of the three.
input AppProblemDismissInput {
  byApp: AppProblemDismissByAppInput                       # an app, its own problems
  byStaffWithIds: AppProblemDismissByStaffWithIdsInput
  byStaffWithKeys: AppProblemDismissByStaffWithKeysInput
}
input AppProblemDismissByAppInput { ids: [ID!], keys: [String!] }   # one or the other
input AppProblemDismissByStaffWithIdsInput { ids: [ID!]! }
input AppProblemDismissByStaffWithKeysInput { keys: [String!]!, app: ID! }

type Mutation {
  # For an app only: adds a problem to the app that calls it.
  appProblemCreate(input: AppProblemCreateInput!): AppProblemCreate   # { appProblem, errors { field message code } }
  # For an app, or staff who may manage apps.
  appProblemDismiss(input: AppProblemDismissInput!): AppProblemDismiss   # { errors { field message code } }
}
```

- An app that reports a key it already has a standing problem for, updated within `aggregationPeriod` minutes, does not get a second problem: that problem's count goes up by one and it takes the new message. With a period of 0 every report is a new problem.
- A problem is critical once its count has reached the `criticalThreshold` of the report; without one it is not critical.
- A dismissed problem stays on record, marked dismissed. If it is reported again it is a new problem.
- An app sees and dismisses only its own problems.

Our own two apps should use it. The payment app reports when the provider refuses its key (the key is invalid, or lacks a permission it needs) and when it cannot verify what the provider sends it (the webhook secret was changed); the email app reports when the mail server refuses it. A refused key is critical from the first time. The message is what staff will read, so it should say what is wrong and what to do. An app that is working must not report anything.

We will call it done when the live shop does it: an app can report and dismiss problems through the API as agreed, staff can read an app's problems in the back office where the installed apps are listed, and our payment and email apps report when the provider or the mail server turns them away. The shop is open while you work: orders are being placed, paid, refunded and confirmed by email, staff are using the back office, and all of that has to keep working.
