# Working in this environment

- The Python environment is at `/venv` and on the PATH. PostgreSQL runs in this container; `DATABASE_URL` is set.
- Run tests with `pytest <path> -n 3 -q -o cache_dir=/tmp/pytest-cache`, for example `pytest saleor/graphql/account/tests/queries -n 3 -q -o cache_dir=/tmp/pytest-cache`. The whole suite (`pytest saleor -n 3`) is about 16,000 tests and takes fifteen to twenty minutes.
- Create migrations with `python manage.py makemigrations`; `python manage.py get_graphql_schema` prints the schema generated from the code.
- This machine has about 8 GB of memory for everything running here: run one test suite at a time.
- `INTERFACE.md` lists the names the hidden tests import that do not exist yet, and the behaviour they check to the letter. Use exactly those names and places.

## The running company

- This repository is a clone of the company's git server (`origin`), which decides who may push where. `main` there is what is deployed and what is judged.
- It runs as the API, at `http://core:8000/graphql/`, with sample data and a staff user (`admin@example.com` / `admin`). A deploy runs its database migrations.
- CI and deploy are at `http://ci:8080/`. Whenever `main` of a repository moves it deploys that repository, then tests the systems together as they run: that each started, that the API answers, that every GraphQL operation the dashboard sends is valid against the schema the running API really has, and that the API, asked as staff for the fields it gained since the work started, answers them without an error in a resolver. `curl http://ci:8080/` shows the latest run and `curl http://ci:8080/runs` every run.
- The other system, `dashboard`: the staff application, served by its development server at `http://dashboard:9000/`, calling the API above.
