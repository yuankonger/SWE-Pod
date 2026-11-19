# Mobile app: owner's notes

- TypeScript, no dependencies. `./run test`, `./run release <version>`, `./run replay <version> <core url>`.
- Modelled on Saleor's React Native example (github.com/saleor/example-react-native-typescript): the app talks
  to Core's GraphQL API directly; there is no server of ours in between.
- `src/operations.ts` holds every operation the app sends, `src/screens.ts` what each screen shows,
  `src/client.ts` the journeys.
- A released build cannot be changed. `releases/<version>/` is each build exactly as shipped, and
  `releases/supported.json` lists the versions customers still run. People update when they choose to, so an
  old build keeps sending its old operations to Core for months.
- Core validates every operation against its schema. If Core removes or renames a field that a supported build
  asks for, that build fails on the whole operation, not just the field.
- From release 1.1.0 a product with several variants is shown with its variant, as the web shop does:
  "Assam Breakfast (100 g)". Release 1.0.0 shows the product name alone and stays supported.
- Money is Core's `Money`: `amount` is a decimal in major units. The app shows no thousands separators.
- The app pays through the app with the identifier `seedco.payments` and passes the card as `{paymentMethod}`.
- A pinned copy of Core's schema is in `pinned/`.
