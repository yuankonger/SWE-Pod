# Health, civic, education, data-collection and science platforms as sources of cross-repo tasks

Method note (applies to every section): `gh` was not installed and the unauthenticated GitHub API allows only 60 calls an hour. So I made blobless, shallow (`--shallow-since=2025-12-01`) clones of 50 upstream repos on 2026-11-18 and mined their default-branch history with `git log`. PR numbers come from squash-merge titles, which carry `(#NNNN)`. Dates are the commit or merge date on the default branch, which is effectively the merge date. Licences come from the LICENSE, COPYING or package.json file at HEAD. Test counts come from file-name patterns in the HEAD tree. Every PR link below matches a commit title that exists upstream. I did not open each PR page, so diff sizes are not given. Where a commit has no PR number (rebase merges, or Moodle's patch workflow), I cite the commit SHA instead. Commit counts mean "commits reachable from HEAD dated 2026-01-01 or later", so they include commits from merged branches.

## Q1. Repos, languages and licences per ecosystem

### Takeaway
The best licences are DHIS2 (BSD-3), ODK (Apache-2.0, with pyxform BSD), OpenMRS (MPL-2.0), CommCare (BSD/Apache), iNaturalist (MIT) and Medplum (Apache, but a monorepo). These are AGPL: Open edX (every repo checked), KoboToolbox kpi, OpenLMIS, CKAN, Ushahidi, Decidim and Consul. These are GPL-3: Moodle core, OpenEMR and OpenProject. Bahmni changed from AGPL-3 to MPL-2.0 in September 2026. Three repos were renamed or folded into others in 2026: ODK web-forms moved into central-frontend, openedx-learning became openedx-core, and edx-platform became openedx-platform.

### Cited findings
**OpenMRS (Java/Spring/Hibernate backend; React/TS "O3" micro-frontends).** Licence is MPL-2.0 for openmrs-core, webservices.rest, fhir2, esm-core, esm-patient-chart, esm-patient-management and esm-laboratory-app (from package.json).
- Sources: [openmrs-core](https://github.com/openmrs/openmrs-core), [REST module](https://github.com/openmrs/openmrs-module-webservices.rest), [FHIR2](https://github.com/openmrs/openmrs-module-fhir2), [esm-core](https://github.com/openmrs/openmrs-esm-core), [patient-chart](https://github.com/openmrs/openmrs-esm-patient-chart), [patient-management](https://github.com/openmrs/openmrs-esm-patient-management)
- Commits since 2026-01-01: core 561, REST 61, fhir2 61, esm-core 313, patient-chart 799, patient-management 554, lab app 294. The newest commit in each is between Oct and Nov 2026.

**Bahmni (OpenMRS-based EMR distribution).** Repos: [bahmni-core](https://github.com/Bahmni/bahmni-core) (Java) and [openmrs-module-bahmniapps](https://github.com/Bahmni/openmrs-module-bahmniapps) (AngularJS).
- The HEAD LICENSE is MPL-2.0. Licence history:
  - PR #302 (2026-06-02): changed to MPL-2.0 with Healthcare Disclaimer.
  - PR #328 (2026-06-05): reverted that change.
  - [BAH-4541 "Release 2.0.0 — final AGPL v3 release" #303](https://github.com/Bahmni/bahmni-core/pull/303), dated 2026-03-30.
  - [BAH-5021 "License Change and Release 3.0.0" #354](https://github.com/Bahmni/bahmni-core/pull/354), dated 2026-09-17.
- Consequence: task start commits before 2026-09-17 are under AGPL-3.0.

**DHIS2 (Java/Spring core; React web apps; Kotlin/Java Android).** All checked repos are BSD-3-Clause:
- [dhis2-core](https://github.com/dhis2/dhis2-core): 1,244 commits in 2026
- [capture-app](https://github.com/dhis2/capture-app): 422
- [maintenance-app-beta](https://github.com/dhis2/maintenance-app-beta) (licence from package.json): 479
- [dhis2-android-sdk](https://github.com/dhis2/dhis2-android-sdk): 995 commits, but the default branch only receives squashed release merges. The latest is "[1.15.0] Version 1.15.0 (#2733)" on 2026-10-14.
- [dhis2-android-capture-app](https://github.com/dhis2/dhis2-android-capture-app): 568
- [app-runtime](https://github.com/dhis2/app-runtime): 47

**ODK (Node.js backend; Vue frontend; Java Android; Python pyxform).** Apache-2.0 for:
- [central-backend](https://github.com/getodk/central-backend): 232 commits in 2026
- [central-frontend](https://github.com/getodk/central-frontend): 598
- [central](https://github.com/getodk/central) (docker-compose umbrella and issue tracker): 215
- [collect](https://github.com/getodk/collect): 1,500
- [javarosa](https://github.com/getodk/javarosa): 109
- [web-forms](https://github.com/getodk/web-forms)

[pyxform](https://github.com/XLSForm/pyxform) is BSD (250 commits in 2026).

The web-forms README now says "This repository is archived. Development of ODK Web Forms has moved to the ODK Central Frontend repository" ([web-forms README](https://github.com/getodk/web-forms)). central-frontend now contains `packages/web-forms`, `packages/xforms-engine` and `packages/xpath` ([central-frontend](https://github.com/getodk/central-frontend)). The last web-forms commit is dated 2026-09-25.

**KoboToolbox.** [kpi](https://github.com/kobotoolbox/kpi) is AGPL-3.0 (Django plus a React "jsapp" in the same repo) and had 1,516 commits in 2026. [kobocat](https://github.com/kobotoolbox/kobocat) is BSD but archived: its README says "archived and has not been maintained since 2024 … KoboCAT has been consolidated into KPI as an application called openrosa". [enketo/enketo](https://github.com/enketo/enketo) is an Apache-2.0 monorepo (from package.json) with 75 commits in 2026.

**Moodle.** [moodle/moodle](https://github.com/moodle/moodle) is GPL-3.0 (COPYING.txt) and had 2,753 commits in 2026. [moodlehq/moodleapp](https://github.com/moodlehq/moodleapp) (Ionic/Angular) is Apache-2.0 and had 804.

**Open edX.** These repos are all AGPL-3.0:
- [edx-platform](https://github.com/openedx/edx-platform) (Django): 1,166 commits in 2026
- [frontend-app-authoring](https://github.com/openedx/frontend-app-authoring) (React): 321
- [frontend-app-learning](https://github.com/openedx/frontend-app-learning): 168
- [frontend-platform](https://github.com/openedx/frontend-platform): 49
- [openedx-learning](https://github.com/openedx/openedx-learning) (Django library): 225

Renames: github.com/openedx/edx-platform now redirects to [openedx/openedx-platform](https://github.com/openedx/openedx-platform), and openedx-learning redirects to [openedx/openedx-core](https://github.com/openedx/openedx-core). [edx-platform #38011 "build!: Switch to openedx-core (renamed from openedx-learning)"](https://github.com/openedx/edx-platform/pull/38011) is dated 2026-02-18.

**OpenLMIS.** [openlmis-requisition](https://github.com/OpenLMIS/openlmis-requisition) (Java, 85 commits in 2026) and [openlmis-requisition-ui](https://github.com/OpenLMIS/openlmis-requisition-ui) (AngularJS, 64) are AGPL-3.0.

**CommCare.** [commcare-hq](https://github.com/dimagi/commcare-hq) (Django) is BSD-3 with 4,910 commits in 2026. [commcare-android](https://github.com/dimagi/commcare-android) (3,627) and [commcare-core](https://github.com/dimagi/commcare-core) (78) are Apache-2.0.

**OpenSRP.** [opensrp/fhircore](https://github.com/opensrp/fhircore) is Apache-2.0 but had only 6 commits in 2026; the last was 2026-09-02. It is low-activity.

**OpenEMR.** [openemr/openemr](https://github.com/openemr/openemr) is GPL-3.0, PHP and a single repo (3,331 commits in 2026).

**Medplum.** [medplum/medplum](https://github.com/medplum/medplum) is Apache-2.0 and a monorepo (`packages/server`, `packages/app`, `packages/react`, `packages/agent` and others), with 2,020 commits in 2026.

**iNaturalist.** All MIT: [inaturalist](https://github.com/inaturalist/inaturalist) (Rails, MIT-LICENSE, 340 commits in 2026), [inaturalistAPI](https://github.com/inaturalist/inaturalistAPI) (Node, package.json, 107) and [iNaturalistReactNative](https://github.com/inaturalist/iNaturalistReactNative) (MIT-LICENSE, 3,638).

**Galaxy.** [galaxyproject/galaxy](https://github.com/galaxyproject/galaxy) is MIT and a monorepo (Python server plus Vue client), with 12,862 commits in 2026.

**CKAN.** [ckan/ckan](https://github.com/ckan/ckan) is AGPL-3.0 (LICENSE.txt) with 824 commits in 2026. I found no LICENSE file at the root of [ckanext-dcat](https://github.com/ckan/ckanext-dcat), which had 39 commits.

**Decidim, Consul, OpenProject, Ushahidi.**
- [decidim/decidim](https://github.com/decidim/decidim) has LICENSE-AGPLv3.txt and is a monorepo of gems.
- [consuldemocracy](https://github.com/consuldemocracy/consuldemocracy) has LICENSE-AGPLv3.txt and is a single repo.
- [opf/openproject](https://github.com/opf/openproject) is GPL-3.0 and a single repo with 19,348 commits.
- [ushahidi/platform](https://github.com/ushahidi/platform) and [platform-client-mzima](https://github.com/ushahidi/platform-client-mzima) are AGPL-3.0 and nearly dormant: 5 and 10 commits in 2026.

### Inferences
- AGPL ecosystems (Open edX, kpi, OpenLMIS, CKAN, Ushahidi, Decidim, Consul): using the code in an internal RL environment is distribution-neutral, and the AGPL network clause is triggered only if a modified version is offered to users over a network. Still, it needs legal sign-off before redistributing environments to labs. GPL-3 (Moodle core, OpenEMR, OpenProject) carries similar obligations when distributed.
- Monorepos (Medplum, Galaxy, Decidim, kpi with its in-repo frontend, enketo) do not fit the "one container per repo" model unless they are split by package. They are weaker candidates.

### Gaps
- I did not check the licence for the Canvas LMS/mobile, HAPI FHIR or GBIF repos; they were not cloned within the time budget.
- I did not check the exact Healthcare Disclaimer wording in the OpenMRS LICENSE; a grep of the first lines did not show it.

## Q2. How the contract between repos is defined

### Takeaway
None of these ecosystems vendors a provider schema into the consumer the way a GraphQL `schema.graphql` would be. The contract is usually a REST API: hand-written OpenAPI in ODK, a generated OpenAPI file committed in Open edX, OpenAPI generated at runtime in DHIS2, kpi and iNat, and Swagger generated at runtime in the OpenMRS REST module. Sometimes it is a spec instead: XForms/ODK XForms for pyxform → javarosa/web-forms/collect, or Moodle web-service function definitions for core → moodleapp. A task needs the contract made explicit, for example by extracting the provider's OpenAPI diff.

### Cited findings
- **ODK**: central-backend keeps a hand-written `docs/api.yaml` (OpenAPI) and a linter, `lib/bin/openapi-docs-lint.js` ([central-backend tree](https://github.com/getodk/central-backend/tree/master/docs)). The frontend has no copy of the schema. Form contract: pyxform compiles XLSForm to ODK XForms, which [javarosa](https://github.com/getodk/javarosa), Collect and web-forms consume.
- **Open edX**: edx-platform commits `docs/lms-openapi.yaml` and `docs/cms-openapi.yaml`, plus a `.github/workflows/generate_openapi_schemas.yml` workflow. The workflow was added by [#39025 "feat: add GH workflow to generate openapi schema"](https://github.com/openedx/edx-platform/pull/39025) on 2026-10-05. The MFEs have no copy of the schema. There are also many FC-0118 "REST API ADR" PRs that standardise APIs, for example [#39078](https://github.com/openedx/edx-platform/pull/39078) on 2026-10-12. MFE extension contract: frontend-plugin-framework slots, for example [frontend-app-learning #1943 "Add course completion slot for Progress Tab"](https://github.com/openedx/frontend-app-learning/pull/1943) on 2026-09-09.
- **DHIS2**: dhis2-core generates OpenAPI at runtime (`dhis-web-api/.../openapi/ApiExtractor.java`, `OpenApiControllerTest.java`) ([dhis2-core](https://github.com/dhis2/dhis2-core)). Web apps consume `/api` via `@dhis2/app-runtime`. Program rules are a shared library (rule-engine) bumped in both core and capture-app; see Q3.
- **OpenMRS**: the REST module generates Swagger at runtime (`omod-common/.../docs/swagger/*.java`) ([REST module](https://github.com/openmrs/openmrs-module-webservices.rest)). FHIR2 exposes FHIR R4. O3 frontends declare the backend modules they need in `routes.json` ([patient-chart #3701 "Declare accurate backend module dependencies in routes.json"](https://github.com/openmrs/openmrs-esm-patient-chart/pull/3701), 2026-09-29). O3 apps share code through the `@openmrs/esm-framework` package from esm-core (extensions, workspaces), which is an MFE contract.
- **KoboToolbox kpi**: it has an `openapi_validator` app and an `openapi.yml` workflow ([kpi](https://github.com/kobotoolbox/kpi)), but the frontend lives in the same repo.
- **iNaturalist API**: it has a `openapi/` directory and `lib/views/swagger_v1.yml.ejs` ([inaturalistAPI](https://github.com/inaturalist/inaturalistAPI)).
- **Moodle**: moodleapp calls core web-service functions through typed wrappers such as `src/core/services/ws.ts` and `*-ws.ts` ([moodleapp](https://github.com/moodlehq/moodleapp)). The contract is the `db/services.php` and external function definitions in core. moodleapp Behat tests run against a real Moodle site, and the app adjusts its tests to core changes, e.g. "MOBILE-4974 behat: Prepare behat for change in MDL-87304" on 2026-01-27 ([moodleapp](https://github.com/moodlehq/moodleapp)).

### Inferences
- ODK (hand-written `api.yaml` changed in the same backend PR) and Open edX (committed generated OpenAPI) are the easiest places to extract a contract artefact per task. For DHIS2 and OpenMRS, you would need to run the server to export OpenAPI/Swagger at both start and solution commits.

### Gaps
- I did not verify whether ODK backend feature PRs reliably update `docs/api.yaml` in the same PR.

## Q3. Concrete multi-repo features in 2026 (verified on default-branch history)

### Takeaway
Six ecosystems yield verified, tightly-timed (0–6 weeks) multi-repo features in 2026:
- **OpenMRS O3**: Jira O3-xxxx keys in commit titles across esm-core, patient-chart and patient-management.
- **Bahmni**: BAH-xxxx keys across bahmni-core (Java) and bahmniapps (JS); a true backend+frontend pairing.
- **ODK**: central-backend + central-frontend, plus pyxform/javarosa/web-forms.
- **Open edX**: openedx-core/learning + edx-platform + frontend-app-authoring.
- **DHIS2**: core + maintenance-app + capture-app, linked by sibling Jira keys under one epic.
- **Moodle**: MDL in core + MOBILE in the app.

OpenLMIS gives a few. CommCare, OpenSRP, Ushahidi and kobocat give essentially none.

### Cited findings

**OpenMRS.** Index: Jira keys O3-xxxx, TRUNK-xxxx, RESTWS-xxxx and FM2-xxxx in squash titles. In 2026, 24 tickets appear in two or more of the cloned OpenMRS and Bahmni repos.
- **O3-5823, diagnosis rank and certainty**:
  - [esm-core #1881 "Add certainty display and blue/gray defaults to diagnosis tags"](https://github.com/openmrs/openmrs-esm-core/pull/1881), 2026-10-02
  - [patient-chart #3621 "Capture diagnosis rank and certainty in the visit note"](https://github.com/openmrs/openmrs-esm-patient-chart/pull/3621), 2026-10-07
- **O3-5986, attachments by encounter**:
  - [esm-core #1887 "Let attachments be recorded on and read by encounter"](https://github.com/openmrs/openmrs-esm-core/pull/1887), 2026-09-18
  - [patient-chart #3668 "Show a visit note's saved images when editing it"](https://github.com/openmrs/openmrs-esm-patient-chart/pull/3668), same day
- **O3-5763, reusable visit summary / visit notes**:
  - patient-chart [#3419](https://github.com/openmrs/openmrs-esm-patient-chart/pull/3419) (2026-07-09), [#3509](https://github.com/openmrs/openmrs-esm-patient-chart/pull/3509) (08-10), [#3569](https://github.com/openmrs/openmrs-esm-patient-chart/pull/3569) (08-18) and [#3595](https://github.com/openmrs/openmrs-esm-patient-chart/pull/3595) (08-27)
  - [patient-management #2600 "Unify the Current visit and Previous visit views"](https://github.com/openmrs/openmrs-esm-patient-management/pull/2600), 2026-08-28
- **O3-5851, visit summary Timeline**:
  - patient-chart [#3534](https://github.com/openmrs/openmrs-esm-patient-chart/pull/3534) (08-19), [#3598](https://github.com/openmrs/openmrs-esm-patient-chart/pull/3598) (08-26) and [#3585 BREAKING "Retire the visit summary Encounters tab"](https://github.com/openmrs/openmrs-esm-patient-chart/pull/3585) (08-31)
  - [patient-management #2711](https://github.com/openmrs/openmrs-esm-patient-management/pull/2711) (09-01, e2e test)
- **O3-6020, encounter object for editing**:
  - [patient-chart #3719](https://github.com/openmrs/openmrs-esm-patient-chart/pull/3719), 2026-10-02
  - patient-management commit, 2026-09-29 ([repo](https://github.com/openmrs/openmrs-esm-patient-management))
- **O3-5836, start visit from patient search**:
  - [patient-management #2640](https://github.com/openmrs/openmrs-esm-patient-management/pull/2640), 2026-07-28
  - [patient-chart #3513](https://github.com/openmrs/openmrs-esm-patient-chart/pull/3513), 2026-07-29
- **O3-5409, batch-action translations**:
  - [esm-core #1584](https://github.com/openmrs/openmrs-esm-core/pull/1584), 2026-03-17
  - [patient-management #2361](https://github.com/openmrs/openmrs-esm-patient-management/pull/2361), 2026-03-26
- **O3-5308, workspace navigation**:
  - [esm-core #1542](https://github.com/openmrs/openmrs-esm-core/pull/1542), 2026-01-06
  - [patient-chart #2922](https://github.com/openmrs/openmrs-esm-patient-chart/pull/2922), same day
- **Backend (Java) pairs**:
  - TRUNK-6674 (drug order duration units): [openmrs-core #6246](https://github.com/openmrs/openmrs-core/pull/6246) and [fhir2 #615](https://github.com/openmrs/openmrs-module-fhir2/pull/615), both 2026-07-08
  - Looser, older pairing on reference ranges: [REST #717 RESTWS-1022 "Support retrieving concept reference ranges for broader context"](https://github.com/openmrs/openmrs-module-webservices.rest/pull/717) (2026-03-13) and [patient-chart #2928 O3-5307 "criteria-based reference ranges in lab results display"](https://github.com/openmrs/openmrs-esm-patient-chart/pull/2928) (2026-02-04)
- Non-feature cross-repo tickets to exclude: O3-5206 RSpack migration, O3-5556 OWASP workflow, O3-5924 dependency cleanup, O3-5042 a11y attribute removal.

**Bahmni.** These are true Java backend + JS frontend pairs:
- **BAH-4869, variable dosage protocols**: [bahmni-core #338](https://github.com/Bahmni/bahmni-core/pull/338) and [bahmniapps #1083](https://github.com/Bahmni/openmrs-module-bahmniapps/pull/1083), both 2026-08-07
- **BAH-4874, draft forms**: [bahmni-core #339](https://github.com/Bahmni/bahmni-core/pull/339) and [bahmniapps #1077](https://github.com/Bahmni/openmrs-module-bahmniapps/pull/1077), both 2026-09-22; follow-ups core #357 and apps #1099
- **BAH-4430, no known allergy**: [bahmni-core #313](https://github.com/Bahmni/bahmni-core/pull/313) and [bahmniapps #1049](https://github.com/Bahmni/openmrs-module-bahmniapps/pull/1049), both 2026-06-28; plus #1076 on 07-29
- **BAH-5197, ADT order / disposition**: [bahmni-core #360](https://github.com/Bahmni/bahmni-core/pull/360) (2026-11-11) and [bahmniapps #1105](https://github.com/Bahmni/openmrs-module-bahmniapps/pull/1105) (2026-11-11)
- **BAH-4917, nurse acknowledgement (backend)**: [bahmni-core #353](https://github.com/Bahmni/bahmni-core/pull/353), 2026-09-18
- Exclude (CI or licence work): BAH-4795, BAH-4802, BAH-5025, BAH-5026, BAH-5021.

**ODK.** Index: umbrella issues in [getodk/central](https://github.com/getodk/central/issues), referenced as `getodk/central#NNNN`. Frontend Web Forms commits use `web-forms#NNN`.
- **Entity "View as" filter**:
  - backend [#1909 "Add viewAs query param to OData and REST entities endpoints"](https://github.com/getodk/central-backend/pull/1909) (2026-08-25) and [#1920 viewAs on CSV/geojson](https://github.com/getodk/central-backend/pull/1920) (08-27)
  - frontend [#1760 "View as (app user) filter on entity list page"](https://github.com/getodk/central-frontend/pull/1760) (08-28), with follow-ups [#1870](https://github.com/getodk/central-frontend/pull/1870) (09-24)
  - Second round, public links: backend [#1955 "Add tokenActive to extended per-form assignments for app users and public links"](https://github.com/getodk/central-backend/pull/1955) (11-10); frontend [#1975](https://github.com/getodk/central-frontend/pull/1975) (11-11) and [#1976](https://github.com/getodk/central-frontend/pull/1976) (11-14)
- **Entity bulk upsert audit event**: backend [#1968 "Migrate audit log event entity.bulk.create to entity.bulk.upsert"](https://github.com/getodk/central-backend/pull/1968) and frontend [#1954 "Use entity.bulk.upsert and add Entity List > Import Data as audit event"](https://github.com/getodk/central-frontend/pull/1954), both 2026-10-23
- **Audit date range (central#2052)**: backend [#1869 "/audits?end: use half-closed date range"](https://github.com/getodk/central-backend/pull/1869) and frontend [#1700 "AuditList: use half-closed date range"](https://github.com/getodk/central-frontend/pull/1700), both 2026-07-21
- **Web Forms autosave (web-forms#573)**: backend commit [2a1a0f7 "adds autosave configuration persistence"](https://github.com/getodk/central-backend/commit/2a1a0f75f80a20a32bf97d1a0594b6f3ab2b549b) (2026-11-10) and frontend commit [2917076 "add option for enabling web forms autosave"](https://github.com/getodk/central-frontend/commit/2917076207728b50a118c9bc02bd1d9810644bf2) (11-16). Neither commit title carries a PR number.
- **Range question tick labels (spec-level, three repos)**:
  - [javarosa #841 "Add support for tick itemset for range"](https://github.com/getodk/javarosa/pull/841), 2026-02-11
  - [pyxform #836 "Insert itemset declaration for range labels"](https://github.com/XLSForm/pyxform/pull/836), 2026-04-12
  - central-frontend (web-forms) [#1937 "add ticks to range question type"](https://github.com/getodk/central-frontend/pull/1937) (10-08) and [#1946](https://github.com/getodk/central-frontend/pull/1946) (10-20)
  - The spread is about 8 months; the javarosa–pyxform pair is 2 months apart.
- **Datetime question type (spec engine)**: [web-forms #783 "adds support to datetime question type"](https://github.com/getodk/web-forms/pull/783) (2026-04-23) and javarosa [#893 "Respect time and datetime binds"](https://github.com/getodk/javarosa/pull/893) (11-03) and [#894 "Datetime arithmetic"](https://github.com/getodk/javarosa/pull/894) (11-11). These look related, but I have not verified that they are the same feature.

**Open edX.** Index: GitHub issues such as `openedx/openedx-core#NNN` and `openedx/openedx-platform#NNNNN`, cited in commit bodies, plus FC-xxxx funded-contribution keys.
- **Separate course and library search indexes**: [edx-platform #39103 "split Studio search into separate course and library indexes"](https://github.com/openedx/edx-platform/pull/39103) and [frontend-app-authoring #3248 "query separate course and library search indexes"](https://github.com/openedx/frontend-app-authoring/pull/3248), both 2026-09-22
- **Remove legacy library content block**: [authoring #3180](https://github.com/openedx/frontend-app-authoring/pull/3180) (2026-08-05) and [edx-platform #38930](https://github.com/openedx/edx-platform/pull/38930) (08-10); both reference openedx-platform#38058
- **Taxonomy type on import**: [openedx-learning #803 "accept taxonomy_type on taxonomy create and import endpoints"](https://github.com/openedx/openedx-learning/pull/803) (2026-09-11) and [authoring #3208 "add taxonomy type selection to import tags wizard"](https://github.com/openedx/frontend-app-authoring/pull/3208) (09-18)
- **Competency-based education (CBE) criteria**, a large multi-PR feature:
  - openedx-learning [#681 GET criteria-groups](https://github.com/openedx/openedx-learning/pull/681) (10-27), [#760 PATCH logic_operator](https://github.com/openedx/openedx-learning/pull/760) (10-29) and [#911 course-run scoping](https://github.com/openedx/openedx-learning/pull/911) (10-30)
  - edx-platform [#39099 CBE API endpoint](https://github.com/openedx/edx-platform/pull/39099) (10-13) and [#39179](https://github.com/openedx/edx-platform/pull/39179) (11-02)
  - authoring [#3275](https://github.com/openedx/frontend-app-authoring/pull/3275) (11-10), [#3354](https://github.com/openedx/frontend-app-authoring/pull/3354) (11-12), [#3358](https://github.com/openedx/frontend-app-authoring/pull/3358) (11-12) and [#3363 "scope competency associations to listed courses"](https://github.com/openedx/frontend-app-authoring/pull/3363) (11-17)
- **System-defined taxonomies replaced by read_only**: openedx-learning commit e92f18e (2026-08-10) and [authoring #3183](https://github.com/openedx/frontend-app-authoring/pull/3183) (08-10) ([openedx-learning](https://github.com/openedx/openedx-learning))
- **Tag usage counts (modular-learning#253)**: [authoring #2957](https://github.com/openedx/frontend-app-authoring/pull/2957) (2026-04-01) and [openedx-learning #506](https://github.com/openedx/openedx-learning/pull/506) (04-13)

**DHIS2.** Index: Jira [DHIS2 project](https://dhis2.atlassian.net). Each repo usually carries its own sibling ticket under one epic, so mining by exact key finds only 3–4 matches (two of them rule-engine version bumps). Matching by topic works better.
- **Custom terminology labels (three repos)**:
  - [maintenance-app #969 "[DHIS2-21624] fields for custom plurals terminology"](https://github.com/dhis2/maintenance-app-beta/pull/969), 2026-06-17
  - [capture-app #4609 "[DHIS2-16610] configurable terminology labels"](https://github.com/dhis2/capture-app/pull/4609), 2026-06-17
  - [dhis2-core #24482 "plural custom-terminology fields for Note, Relationship and Attribute [DHIS2-21738]"](https://github.com/dhis2/dhis2-core/pull/24482), 2026-07-21
  - [maintenance-app #1006 "[DHIS2-21877] new plural terminology fields"](https://github.com/dhis2/maintenance-app-beta/pull/1006), 08-14
  - [capture-app #4727 "[DHIS2-21635] Display custom terminology labels across UI"](https://github.com/dhis2/capture-app/pull/4727), 09-29
- **Change-log toggle**: [maintenance-app #1046 "[DHIS2-22184] Changelog toggle for TET and program"](https://github.com/dhis2/maintenance-app-beta/pull/1046) (2026-10-18) and [capture-app #4795 "[DHIS2-22185] Use enableChangeLog"](https://github.com/dhis2/capture-app/pull/4795) (10-31). I found no core commit with a matching title.
- **Enrollment attribute option combo (AOC)**:
  - [maintenance-app #1041 "[DHIS2-21796] enrollment category combination field"](https://github.com/dhis2/maintenance-app-beta/pull/1041), 2026-09-30
  - [capture-app #4752 [DHIS2-21797]](https://github.com/dhis2/capture-app/pull/4752) (10-09) and [#4753](https://github.com/dhis2/capture-app/pull/4753) (10-11)
  - core [#24389 "AOCs into analytics enrollment tables"](https://github.com/dhis2/dhis2-core/pull/24389) (07-08), [#25802](https://github.com/dhis2/dhis2-core/pull/25802) (10-27) and [#25936](https://github.com/dhis2/dhis2-core/pull/25936) (10-29)
- **Rule-engine z-score fix (DHIS2-22201)**: [core #25594](https://github.com/dhis2/dhis2-core/pull/25594) (2026-10-09) and [capture-app #4788](https://github.com/dhis2/capture-app/pull/4788) (10-15). Both are mostly a dependency bump.
- Android: the default branches of android-sdk and android-capture-app contain only release squashes and merge commits, so per-feature PRs are not visible on `master`/`main` (e.g. [android-sdk #2733](https://github.com/dhis2/dhis2-android-sdk/pull/2733) "Version 1.15.0"). Mining them would need the `develop` branch.

**Moodle.** Index: [tracker.moodle.org](https://tracker.moodle.org), with MDL keys for core and MOBILE keys for the app. Core lands by integration merge, not GitHub PRs.
- **MDL-87544, enablemycourses exposed to the app**: core commit [046112c8 "MDL-87544 tool_mobile: expose enablemycourses via webservices"](https://github.com/moodle/moodle/commit/046112c8) (2026-03-06), then app commit [e733300 "MOBILE-4999 my: Check new enablemycourses setting"](https://github.com/moodlehq/moodleapp/commit/e733300) (2026-03-27)
- **MDL-89346, per-marker feedback**: core commit [7076b96d "MDL-89346 mod_assign: Expose per-marker feedback via webservice"](https://github.com/moodle/moodle/commit/7076b96d) (2026-09-15, merged 09-17), then MOBILE-5080 app commits from 2026-10-06 to 11-13, e.g. [ab86e07 "assign: Show multiple markers feedback info"](https://github.com/moodlehq/moodleapp/commit/ab86e07)
- **MDL-88229, custom user-menu items key**: [core 154ef004](https://github.com/moodle/moodle/commit/154ef004) (2026-03-23); the app re-enabled a Behat scenario on 03-27

**OpenLMIS.**
- **OLMIS-8176, pack size**: [requisition #130](https://github.com/OpenLMIS/openlmis-requisition/pull/130) and [requisition-ui #86](https://github.com/OpenLMIS/openlmis-requisition-ui/pull/86), both 2026-08-20
- **OLMIS-8403 / OLMIS-8378, supplying-facility stock column**: [requisition-ui #97](https://github.com/OpenLMIS/openlmis-requisition-ui/pull/97) (2026-10-12) and a requisition commit on 10-13

**Weak or none.**
- CommCare: mining all `[A-Z]+-NNN` keys across hq, android and core found zero shared tickets in 2026 ([commcare-hq](https://github.com/dimagi/commcare-hq)).
- Ushahidi: 5 and 10 commits in 2026.
- kobocat: archived.
- OpenSRP fhircore: 6 commits in 2026.

### Inferences
- Best fit to the Saleor template (backend + frontend, separate repos, separate test suites):
  1. Bahmni: Java Maven + JS, same-day merges with the same ticket key.
  2. ODK central-backend + central-frontend: Node + Vue, hand-written OpenAPI, same-day or next-day pairs.
  3. Open edX core/platform + authoring MFE: AGPL.
  4. DHIS2 core + maintenance/capture apps.
- OpenMRS O3 pairs are mostly frontend+frontend: esm-core is the framework library, the apps are its consumers. That is still a valid two-repo contract through the `@openmrs/esm-framework` API, but backend+frontend pairs (REST/FHIR2 with O3) are rare in 2026.

### Gaps
- PR diff sizes and per-PR test files were not checked; the unauthenticated API budget was too small.
- I did not verify that the ODK autosave commits belong to specific PR numbers.
- Canvas LMS + canvas-ios/android, HAPI FHIR + hapi-fhir-jpaserver-starter, GBIF and CKAN core + ckanext-* pairs were not mined.

## Q4. Test suites (framework, size, Docker/offline viability)

### Takeaway
Every strong candidate has substantial unit and integration suites that can run in Docker. External dependencies are usually just Postgres or MySQL; Open edX also needs MongoDB, and Moodle app end-to-end tests need a real Moodle site. I did not measure runtimes, so treat the notes below as inferences.

### Cited findings (test-file counts from the HEAD tree, by name pattern)
- **OpenMRS**:
  - Java JUnit: core 446 files, REST 286, fhir2 350
  - Jest: esm-core 173, patient-chart 220, patient-management 174
  - Playwright end-to-end directories: 18, 70 and 50 files respectively
  - Source: [openmrs-esm-patient-chart](https://github.com/openmrs/openmrs-esm-patient-chart)
- **Bahmni**: bahmni-core 197 Java test files and bahmniapps 333 JS spec files ([bahmni-core](https://github.com/Bahmni/bahmni-core)).
- **DHIS2**:
  - dhis2-core: 1,876 Java test files, including `dhis-test-web-api`
  - capture-app: 51 unit files plus 98 end-to-end/Cypress files
  - maintenance-app-beta: 133
  - android-sdk: 850 `*Should`/`*Test` files
  - android-capture-app: 284
  - Source: [dhis2-core](https://github.com/dhis2/dhis2-core)
- **ODK**:
  - central-backend: 166 mocha files under `test/`, which need Postgres; it has a `docker-postgres` make target and [#1924 "docker-postgres: wait for startup deterministically"](https://github.com/getodk/central-backend/pull/1924)
  - central-frontend: 496 spec files plus 133 end-to-end files
  - javarosa: 103; pyxform: 78 (pytest); collect: 537; web-forms: 184
  - Source: [central-backend](https://github.com/getodk/central-backend)
- **Open edX**:
  - edx-platform: 1,028 Python test files (pytest; needs MySQL and MongoDB)
  - frontend-app-authoring: 617 (Jest)
  - openedx-learning: 60; frontend-app-learning: 124
  - Source: [frontend-app-authoring](https://github.com/openedx/frontend-app-authoring)
- **Moodle**: core has 3,808 PHPUnit and Behat files; moodleapp has 245 ([moodle](https://github.com/moodle/moodle)).
- **OpenLMIS**: requisition 239 and requisition-ui 90. **kpi**: 273. **enketo**: 164. **CKAN**: 232. **CommCare**: hq 1,207, android 295. **Medplum**: 1,021. **iNat**: rails 344, API 95, RN 294.

### Inferences
- Lightest to containerise: pyxform (pure pytest), javarosa (Gradle JUnit), ODK central-backend (Node + Postgres), OpenMRS esm repos (Jest only), Bahmni and OpenMRS Java (Maven + H2 for unit tests).
- Heaviest: edx-platform (full suite is very long; select the target test modules), dhis2-core (integration tests use Testcontainers Postgres, which needs Docker-in-Docker), Moodle Behat and moodleapp Behat (they need a live Moodle).

### Gaps
- No measured runtimes or exact test-case counts (only files were counted). I did not verify that each suite runs with networking disabled; npm and Maven dependencies would need pre-fetching.

## Q5. 2026 activity and estimated minable cross-repo features per year

### Takeaway
Estimated yield of clean multi-repo features per year:
- Open edX: about 10–20 (rich, but AGPL)
- OpenMRS + Bahmni: about 10–15, plus a long tail of O3 frontend pairs
- DHIS2: about 10–20 by topic matching (needs manual pairing)
- ODK: about 8–12
- Moodle: about 5–10 (GPL core plus Apache app)
- OpenLMIS: about 2–4

The best index mechanisms are Jira keys in squash titles (OpenMRS O3/TRUNK/RESTWS, Bahmni BAH, OpenLMIS OLMIS, Moodle MDL/MOBILE), the ODK `getodk/central#` umbrella issues, and Open edX `openedx/*#` issue references in commit bodies.

### Cited findings
- Shared tickets in 2026 by exact key: 24 across OpenMRS and Bahmni repos, about 11 of them feature-like (counts from git-log mining; examples in Q3).
- Open edX: 9 `openedx/*#NNN` issue references appear in two or more repos. More pairs appear only by topic, such as the search split and CBE ([edx-platform](https://github.com/openedx/edx-platform)).
- DHIS2 by exact key: 4 shared Jira keys in 2026. Topic matching gives at least 3 strong multi-repo epics (terminology, change log, enrollment AOC) ([maintenance-app-beta](https://github.com/dhis2/maintenance-app-beta)).
- ODK by exact reference: 8 `getodk/central#` issues across backend, frontend and central in 2026, mostly CI or infrastructure. Topic matching gives 4–5 feature pairs ([central-frontend](https://github.com/getodk/central-frontend)).
- Moodle: moodleapp references 6 distinct MDL keys in 2026, plus the MOBILE-5080 / MDL-89346 pair ([moodleapp](https://github.com/moodlehq/moodleapp)).
- OpenLMIS: 2 shared OLMIS keys in 2026.

### Inferences
- Priority ranking for this RL environment, balancing licence, separation and test quality:
  1. **ODK** (Apache/BSD; Node backend + Vue frontend; XForms spec across pyxform/javarosa)
  2. **Bahmni/OpenMRS** (MPL-2.0; Java + JS; Jira-key index; check AGPL status before 2026-09-17 for Bahmni)
  3. **DHIS2** (BSD; Java + React; needs topic pairing)
  4. **Open edX** (richest multi-repo, but AGPL)
  5. **Moodle core + app** (GPL core)
- Avoid Medplum, Galaxy, Decidim and kpi as multi-repo sources because they are monorepos, and OpenSRP, Ushahidi and kobocat because they are dormant or archived.

### Gaps
- Yearly yields are extrapolations from about 10.5 months of 2026 history in the cloned subset. Other O3 apps (dispensing, stock, billing, ward) and other DHIS2 apps (data-visualizer, maps, aggregate data entry) were not cloned and would raise the estimates.
- Canvas LMS, HAPI FHIR, CKAN extensions and GBIF were not assessed.
