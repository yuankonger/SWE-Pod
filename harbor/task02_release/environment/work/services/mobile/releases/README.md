# Released builds

Each directory is one released version of the app, exactly as it was built: the operations it sends to Core and
the code that turns Core's answers into screens. These builds are on customers' phones. They cannot be changed,
and customers update when they choose to, so every version in `supported.json` keeps talking to Core for months.

- `supported.json` lists the versions still in use. Core must keep working with all of them.
- `./run release <version>` freezes the current source as a new build.
- `./run replay <version> <core url>` buys something the way that build does, against a running Core.
