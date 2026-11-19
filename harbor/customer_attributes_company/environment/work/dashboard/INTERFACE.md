# What the hidden tests rely on

The work is judged by the project's own tests, which you cannot see. They use the names below. Each must
exist at exactly this place under exactly this name, declared as shown (every parameter and property), or
the tests that use it cannot run. This says where things live and what they are called, not what they do.

## Names that do not exist yet

### `src/components/ConditionalFilter/API/Handler.ts`
- `CustomerTypeHandler`: `export class CustomerTypeHandler implements Handler`

### `src/components/ConditionalFilter/API/filterChoicesPage.ts`  (new file)
- `FILTER_CHOICES_PAGE_SIZE`: `export const FILTER_CHOICES_PAGE_SIZE = DEFAULT_INITIAL_SEARCH_DATA.first;`
- `NO_MORE_CHOICES`: `export const NO_MORE_CHOICES: FilterChoicesPageInfo = ; export interface FilterChoicesPageInfo { hasNextPage: boolean; endCursor: string | null; }`
- `appendUniqueOptions`: `export const appendUniqueOptions = <T extends { value: string }>( existing: T[], incoming: T[], ): T[] => ...`
- `createChoiceFetchState`: `export const createChoiceFetchState = (): ChoiceFetchState => ... ; export interface ChoiceFetchState { generations: Record<string, number>; pageInfo: Record<string, FilterChoicesPageInfo>; query: Record<string, string>; fetchMoreInFlight: Record<string, boolean>; }`
- `emptyChoicesPage`: `export const emptyChoicesPage = <T = ItemOption>(): FilterChoicesPage<T> => ... ; export interface FilterChoicesPage<T = ItemOption> { options: T[]; pageInfo: FilterChoicesPageInfo; }`
- `fetchHandlerPage`: `export const fetchHandlerPage = async <T = ItemOption>( handler: { fetch: (after?: string | null) => Promise<unknown[]>; pageInfo?: FilterChoicesPageInfo; }, after?: string | null, ): Promise<FilterChoicesPage<T>> => ... ; export interface FilterChoicesPageInfo { hasNextPage: boolean; endCursor: string | null; } ; export interface FilterChoicesPage<T = ItemOption> { options: T[]; pageInfo: FilterChoicesPageInfo; }`
- `hasSameChoiceQuery`: `export const hasSameChoiceQuery = ( state: ChoiceFetchState, fetchKey: string, inputValue: string, ): boolean => ... ; export interface ChoiceFetchState { generations: Record<string, number>; pageInfo: Record<string, FilterChoicesPageInfo>; query: Record<string, string>; fetchMoreInFlight: Record<string, boolean>; }`
- `hydrateChoiceCount`: `export const hydrateChoiceCount = (ids: string[]): number => ...`
- `isCurrentChoiceGeneration`: `export const isCurrentChoiceGeneration = ( state: ChoiceFetchState, fetchKey: string, generation: number, ): boolean => ... ; export interface ChoiceFetchState { generations: Record<string, number>; pageInfo: Record<string, FilterChoicesPageInfo>; query: Record<string, string>; fetchMoreInFlight: Record<string, boolean>; }`
- `pageInfoFromConnection`: `export const pageInfoFromConnection = ( connection?: { pageInfo?: { hasNextPage: boolean; endCursor?: string | null; } | null; } | null, ): FilterChoicesPageInfo => ... ; export interface FilterChoicesPageInfo { hasNextPage: boolean; endCursor: string | null; }`
- `startAppendChoiceFetch`: `export const startAppendChoiceFetch = ( state: ChoiceFetchState, fetchKey: string, ): number | null => ... ; export interface ChoiceFetchState { generations: Record<string, number>; pageInfo: Record<string, FilterChoicesPageInfo>; query: Record<string, string>; fetchMoreInFlight: Record<string, boolean>; }`
- `startReplaceChoiceFetch`: `export const startReplaceChoiceFetch = ( state: ChoiceFetchState, fetchKey: string, inputValue: string, ): number => ... ; export interface ChoiceFetchState { generations: Record<string, number>; pageInfo: Record<string, FilterChoicesPageInfo>; query: Record<string, string>; fetchMoreInFlight: Record<string, boolean>; }`

### `src/components/ConditionalFilter/API/initialState/customers/InitialCustomerState.ts`  (new file)
- `InitialCustomerStateResponse`: `export class InitialCustomerStateResponse implements InitialCustomerState, AttributeLookup`

### `src/components/ConditionalFilter/FilterElement/index.ts`
- `FilterContainer`: `(exported at the target)`

### `src/components/ConditionalFilter/FiltersQueryBuilder/queryVarsBuilders/AssignedAttributeQueryVarsBuilder.ts`  (new file)
- `AssignedAttributeQueryVarsBuilder`: `export class AssignedAttributeQueryVarsBuilder implements WhereOnlyQueryVarsBuilder<AssignedAttributeFilterQueryPart>`

### `src/components/ConditionalFilter/FiltersQueryBuilder/queryVarsBuilders/CustomerTypeQueryVarsBuilder.ts`  (new file)
- `CustomerTypeQueryVarsBuilder`: `export class CustomerTypeQueryVarsBuilder implements BothApiQueryVarsBuilder<`

### `src/components/ConditionalFilter/UI/resolveAsyncComboboxState.ts`  (new file)
- `includeSelectedComboboxOptions`: `export const includeSelectedComboboxOptions = <T extends ComboboxOptionIdentity>( options: T[], selected?: T | T[] | string | null, ): T[] => ... ; export interface ComboboxOptionIdentity { label: string; value: string; slug?: string | null; }`
- `isSelectedComboboxLabel`: `export const isSelectedComboboxLabel = (selected: unknown, inputValue: string): boolean => ...`
- `isSelectedMultiselectLabel`: `export const isSelectedMultiselectLabel = (selected: unknown, inputValue: string): boolean => ...`
- `resolveComboboxValue`: `export const resolveComboboxValue = <T extends ComboboxOptionIdentity>( options: T[], selected?: T | string | null, ): T | null => ... ; export interface ComboboxOptionIdentity { label: string; value: string; slug?: string | null; }`

### `src/components/ConditionalFilter/UI/resolveAttributeComboboxState.ts`  (new file)
- `resolveAttributeComboboxOptions`: `export const resolveAttributeComboboxOptions = ( options: LeftOperatorOption[], selected?: SelectedAttributeOption | null, ): LeftOperatorOption[] => ... ; type SelectedAttributeOption = Pick<LeftOperatorOption, "label" | "value" | "type">`
- `resolveAttributeComboboxValue`: `export const resolveAttributeComboboxValue = ( options: LeftOperatorOption[], selected?: SelectedAttributeOption | null, ): LeftOperatorOption | null => ... ; type SelectedAttributeOption = Pick<LeftOperatorOption, "label" | "value" | "type">`

### `src/components/ConditionalFilter/ValueProvider/TokenArray/fetchingParams.ts`
- `toCustomerFetchingParams`: `export const toCustomerFetchingParams = (p: CustomerFetchingParams, c: UrlToken) => ... ; export interface CustomerFetchingParams { customerType: string[]; attribute: Record<string, string[]>; attributeReference: Record<string, string[]>; }`

### `src/components/ConditionalFilter/ValueProvider/navigationQueryParams.ts`
- `getNavigationQueryParams`: `export const getNavigationQueryParams = ( locationSearch: string, providerType: FilterProviderType, ): Record<string, string[]> => ...`

### `src/components/ConditionalFilter/queryVariables.ts`
- `createCustomerWhereVariables`: `export const createCustomerWhereVariables = (value: FilterContainer): CustomerWhereInput => ... ; type CustomerWhereInput,`

### `src/components/CustomerType/CustomerType.tsx`  (new file)
- `ClickableCustomerType`: `export const ClickableCustomerType = (props: CustomerTypeProps): JSX.Element => ... ; interface CustomerTypeProps { /** * The customer type to display. Pass `undefined` to render a skeleton placeholder while loading. */ customerType: CustomerTypeLike | undefined; /** * Hide the leading customer type icon. * @default false */ hideIcon?: boolean; /** * Macaw text size token used for the label. * @default 2 */ size?: CustomerTypeTextSize; /** * Macaw text color token used for the label. * @default "default2" */ color?: TextProps["color"]; /** * Optional override for the `data-test-id` attribute. * @default "customer-type-display" */ "data-test-id"?: string; /** * Native hover tooltip for the customer type name. * @default customerType.name */ title?: string; /** * When set, the chip links here instead of the filtered customer list. * Callers must already have decided the user may open this destination. */ href?: string; }`
- `CustomerTypeDisplay`: `export const CustomerTypeDisplay = ({ customerType, hideIcon = false, size = 2, color = "default2", "data-test-id": dataTestId = "customer-type-display", title, }: CustomerTypeProps): JSX.Element => ... ; interface CustomerTypeProps { /** * The customer type to display. Pass `undefined` to render a skeleton placeholder while loading. */ customerType: CustomerTypeLike | undefined; /** * Hide the leading customer type icon. * @default false */ hideIcon?: boolean; /** * Macaw text size token used for the label. * @default 2 */ size?: CustomerTypeTextSize; /** * Macaw text color token used for the label. * @default "default2" */ color?: TextProps["color"]; /** * Optional override for the `data-test-id` attribute. * @default "customer-type-display" */ "data-test-id"?: string; /** * Native hover tooltip for the customer type name. * @default customerType.name */ title?: string; /** * When set, the chip links here instead of the filtered customer list. * Callers must already have decided the user may open this destination. */ href?: string; }`

### `src/components/Sidebar/menu/createCustomerTypeMenuItems.ts`  (new file)
- `CUSTOMER_TYPE_NAV_ALL_ID`: `export const CUSTOMER_TYPE_NAV_ALL_ID = `${CUSTOMER_TYPE_NAV_ID_PREFIX}all`;`
- `CUSTOMER_TYPE_NAV_ID_PREFIX`: `export const CUSTOMER_TYPE_NAV_ID_PREFIX = "customer-type-nav-";`
- `MAX_CUSTOMER_TYPE_NAV_TYPES`: `export const MAX_CUSTOMER_TYPE_NAV_TYPES = 8;`
- `createCustomerTypeMenuItems`: `export const createCustomerTypeMenuItems = ({ customerTypes, allLabel, pinnedIds = [], selectedTypeIds = [], }: { customerTypes: Array<{ id: string; name: string }>; allLabel: string; pinnedIds?: string[]; selectedTypeIds?: string[]; }): SidebarMenuItem[] => ...`
- `getCustomerTypeIdsFromSearch`: `export const getCustomerTypeIdsFromSearch = (search: string): string[] => ...`
- `isCustomerTypeNavItem`: `export const isCustomerTypeNavItem = (menuItem: Pick<SidebarMenuItem, "id">): boolean => ...`
- `selectCustomerTypesForNav`: `export const selectCustomerTypesForNav = ({ customerTypes, pinnedIds, selectedTypeIds, limit = MAX_CUSTOMER_TYPE_NAV_TYPES, }: { customerTypes: Array<{ id: string; name: string }>; pinnedIds: string[]; selectedTypeIds: string[]; limit?: number; }): Array<{ id: string; name: string }> => ...`

### `src/customerTypes/components/CreateCustomerTypeDialog/CreateCustomerTypeDialog.tsx`  (new file)
- `CreateCustomerTypeDialog`: `export const CreateCustomerTypeDialog = ({ open, confirmButtonState, disabled = false, errors: apiErrors, onClose, onSubmit, }: CreateCustomerTypeDialogProps): JSX.Element => ... ; interface CreateCustomerTypeDialogProps { open: boolean; confirmButtonState: ConfirmButtonTransitionState; disabled?: boolean; errors: CustomerTypeCreateErrorFragment[]; onClose: () => void; onSubmit: (data: CreateCustomerTypeFormData) => SubmitPromise<CustomerTypeCreateErrorFragment[]>; }`

### `src/customerTypes/components/CustomerTypeAttributes/CustomerTypeAttributes.tsx`  (new file)
- `CustomerTypeAttributes`: `export const CustomerTypeAttributes = ({ attributes, disabled, type, onAttributeAssign, onAttributeCreate, onAttributeReorder, onAttributeUnassign, ...listActions }: CustomerTypeAttributesProps): JSX.Element => ... ; interface CustomerTypeAttributesProps extends ListActions { attributes: AssignedCustomerTypeAttribute[] | undefined; disabled: boolean; type: AttributeTypeEnum; onAttributeAssign: (type: AttributeTypeEnum) => void; onAttributeCreate: (type: AttributeTypeEnum) => void; onAttributeReorder: ReorderAction; onAttributeUnassign: (id: string) => void; }`

### `src/customerTypes/components/CustomerTypeDetails/CustomerTypeDetails.tsx`  (new file)

### `src/customerTypes/components/CustomerTypeDetailsPage/CustomerTypeDetailsPage.tsx`  (new file)
- `CustomerTypeDetailsPage`: `export const CustomerTypeDetailsPage = (props: CustomerTypeDetailsPageProps) => ... ; interface CustomerTypeDetailsPageProps { errors: CustomerTypeUpdateErrorFragment[]; customerType: CustomerTypeDetailsFragment | undefined; disabled: boolean; attributeList: ListActions; saveButtonBarState: ConfirmButtonTransitionState; onAttributeAdd: (type: AttributeTypeEnum) => void; onAttributeCreate: (type: AttributeTypeEnum) => void; onAttributeReorder: (event: ReorderEvent, type: AttributeTypeEnum) => void; onAttributeUnassign: (id: string) => void; onDelete: () => void; onSetDefault: () => void; onShowMetadata: () => void; onSubmit: (data: CustomerTypeForm) => void; }`
- `CustomerTypeForm`: `export interface CustomerTypeForm extends MetadataFormData { name: string; slug: string; attributes: Option[]; }`

### `src/customerTypes/components/CustomerTypeDetailsPage/Title.tsx`  (new file)
- `CustomerTypeDetailsTitle`: `export const CustomerTypeDetailsTitle = ({ customerType, loading, }: CustomerTypeDetailsTitleProps) => ... ; interface CustomerTypeDetailsTitleProps { customerType?: CustomerTypeDetailsHeaderCustomerType | null; loading?: boolean; }`

### `src/customerTypes/components/CustomerTypeMetadataDialog/CustomerTypeMetadataDialog.tsx`  (new file)
- `CustomerTypeMetadataDialog`: `export const CustomerTypeMetadataDialog = ({ onClose, open, customerType, refetchCustomerType, }: CustomerTypeMetadataDialogProps) => ... ; interface CustomerTypeMetadataDialogProps { open: boolean; onClose: () => void; customerType: CustomerTypeWithOptionalPrivateMetadata | undefined | null; refetchCustomerType?: () => Promise<ApolloQueryResult<CustomerTypeDetailsQuery>>; }`

### `src/customerTypes/handlers/customerTypeAttributeCreateHandler.ts`  (new file)
- `CustomerTypeAttributeCreateMutations`: `export interface CustomerTypeAttributeCreateMutations { attributeCreate: (options: { variables: { input: AttributeCreateInput } }) => Promise<{ data?: { attributeCreate?: { attribute?: { id: string } | null; errors: AttributeErrorFragment[]; }; }; }>; assignCreatedAttribute: (options: { variables: { customerTypeId: string; attributeIds: string[] }; }) => Promise<{ data?: { customerTypeAssignAttributes?: { errors: CustomerTypeAssignAttributesErrorFragment[]; }; }; }>; }`
- `executeCustomerTypeAttributeCreate`: `export async function executeCustomerTypeAttributeCreate( { customerTypeId, formData, values, createFailedMessage, formatAssignErrors, }: CustomerTypeAttributeCreateParams, { attributeCreate, assignCreatedAttribute }: CustomerTypeAttributeCreateMutations, ): Promise<CustomerTypeAttributeCreateOutcome> ; export interface CustomerTypeAttributeCreateParams { customerTypeId: string; formData: AttributePageFormData; values: AttributeValueEditDialogFormData[]; createFailedMessage: string; formatAssignErrors: (errors: CustomerTypeAssignAttributesErrorFragment[]) => string; } ; export interface CustomerTypeAttributeCreateMutations { attributeCreate: (options: { variables: { input: AttributeCreateInput } }) => Promise<{ data?: { attributeCreate?: { attribute?: { id: string } | null; errors: AttributeErrorFragment[]; }; }; }>; assignCreatedAttribute: (options: { variables: { customerTypeId: string; attributeIds: string[] }; }) => Promise<{ data?: { customerTypeAssignAttributes?: { errors: CustomerTypeAssignAttributesErrorFragment[]; }; }; }>; } ; export interface CustomerTypeAttributeCreateOutcome extends CreateMetadataHandlerFunctionResult<AttributeErrorFragment> { assignErrorMessage?: string; }`

### `src/customerTypes/urls.ts`  (new file)
- `customerTypeListUrl`: `export const customerTypeListUrl = (params?: CustomerTypeListUrlQueryParams) => ... ; export type CustomerTypeListUrlQueryParams = ActiveTab & Dialog<CustomerTypeListUrlDialog> & Pagination & CustomerTypeListUrlFilters & CustomerTypeListUrlSort`
- `customerTypesPath`: `export const customerTypesPath = customerTypesSection;`

### `src/customerTypes/utils/customerTypePageForm.ts`  (new file)
- `isCustomerTypeUpdateFormPristine`: `export function isCustomerTypeUpdateFormPristine( data: CustomerTypeForm, initialData: CustomerTypeForm, ): boolean`

### `src/customers/components/CustomerAttributesCard/CustomerAttributesCard.tsx`  (new file)
- `CustomerAttributesCard`: `export const CustomerAttributesCard = ({ children, selectedType, savedTypeId, disabled, error, onChange, }: CustomerAttributesCardProps): JSX.Element => ... ; interface CustomerAttributesCardProps { children?: ReactNode; selectedType: CustomerTypeOption | null; /** Currently saved type. Used to skip the confirm dialog when reverting. */ savedTypeId: string | null; disabled: boolean; error?: string; onChange: (type: CustomerTypeOption) => void; }`

### `src/customers/components/CustomerDetailsPage/Title.tsx`  (new file)
- `CustomerDetailsTitle`: `export const CustomerDetailsTitle = ({ customer, loading, }: CustomerDetailsTitleProps): JSX.Element | null => ... ; interface CustomerDetailsTitleProps { customer?: CustomerDetailsHeaderCustomer | null; loading?: boolean; }`

### `src/customers/components/CustomerDetailsPage/saveComposition.ts`  (new file)
- `buildCustomerSaveComposition`: `export const buildCustomerSaveComposition = ({ attributesDirty, data, initial, }: { attributesDirty: boolean; data: CustomerDetailsIdentityForm; initial: CustomerDetailsIdentityForm; }): CustomerSaveComposition => ... ; interface CustomerDetailsIdentityForm { customerTypeId: string; email: string; firstName: string; lastName: string; note: string; } ; export interface CustomerSaveComposition { hasAttributes: boolean; hasGeneral: boolean; hasType: boolean; }`
- `hasCustomerSaveComposition`: `export const hasCustomerSaveComposition = (composition: CustomerSaveComposition): boolean => ... ; export interface CustomerSaveComposition { hasAttributes: boolean; hasGeneral: boolean; hasType: boolean; }`

### `src/customers/components/CustomerListPage/CustomerListPage.tsx`
- `CustomerListPage`: `export const CustomerListPage = ({ initialSearch, onSearchChange, selectedCustomerIds, onCustomersDelete, onCreateCustomerType, customerTypes, selectedTypeIds, activeCustomerTypeName, tabCounts, onTabChange, ...customerListProps }: CustomerListPageProps): JSX.Element => ... ; interface CustomerListPageProps extends PageListProps, SearchPageProps, SortPage<CustomerListUrlSortField> { customers: Customers | undefined; selectedCustomerIds: string[]; loading: boolean; onSelectCustomerIds: (rows: number[], clearSelection: () => void) => void; onCustomersDelete: () => void; onCreateCustomerType: () => void; customerTypes: Array<{ id: string; name: string }> | undefined; selectedTypeIds: string[]; activeCustomerTypeName: string | undefined; tabCounts: Record<string, CustomerTypeTabCount | undefined>; onTabChange: (ids: string[]) => void; }`

### `src/customers/components/CustomerOrders/CustomerOrders.tsx`
- `CustomerOrders`: `export const CustomerOrders = ({ orders, viewAllHref }: CustomerOrdersProps): JSX.Element => ... ; interface CustomerOrdersProps { orders: Array<CustomerRecentOrder | null | undefined> | undefined; viewAllHref: string; }`

### `src/customers/components/CustomerTypeCard/ChangeCustomerTypeDialog.tsx`  (new file)
- `ChangeCustomerTypeDialog`: `export const ChangeCustomerTypeDialog = ({ open, typeName, onClose, onConfirm, }: ChangeCustomerTypeDialogProps): JSX.Element => ... ; interface ChangeCustomerTypeDialogProps { open: boolean; typeName: string; onClose: () => void; onConfirm: () => void; }`

### `src/customers/components/CustomerTypeTabs/CustomerTypeTabs.tsx`  (new file)

### `src/customers/hooks/useCustomerDetailsAttributes.ts`  (new file)

### `src/customers/urls.ts`
- `customerListUrlWithCustomerType`: `export const customerListUrlWithCustomerType = (customerType?: { id: string }) => ...`

### `src/customers/utils/customerAttributes.ts`  (new file)
- `customerAttributeInputHasValue`: `export const customerAttributeInputHasValue = (input: AttributeValueInput): boolean => ... ; type AttributeValueInput,`
- `getAttributeInputFromCustomer`: `export const getAttributeInputFromCustomer = ( customer: | { assignedAttributes?: CustomerAssignedAttributeFragment[] | null; customerType?: CustomerTypeOnCustomerFragment | null; } | null | undefined, ): AttributeInput[] => ... ; type CustomerAssignedAttributeFragment, ; type CustomerTypeOnCustomerFragment,`
- `getAttributeInputFromCustomerType`: `export const getAttributeInputFromCustomerType = ({ assignedAttributes = [], customerType, previousAttributes = [], }: { assignedAttributes?: CustomerAssignedAttributeFragment[]; customerType: CustomerTypeOnCustomerFragment | null | undefined; previousAttributes?: AttributeInput[]; }): AttributeInput[] => ... ; type CustomerAssignedAttributeFragment, ; type CustomerTypeOnCustomerFragment,`
- `getCustomerUpdateAttributesInput`: `export const getCustomerUpdateAttributesInput = ({ attributes, prevAttributes, typeChanged, updatedFileAttributes, }: { attributes: AttributeInput[]; prevAttributes: AttributeInput[] | null; typeChanged: boolean; updatedFileAttributes: AttributeValueInput[]; }): AttributeValueInput[] | undefined => ... ; type AttributeValueInput,`
- `mapAssignedAttribute`: `export const mapAssignedAttribute = ( assigned: CustomerAssignedAttributeFragment, ): MappedAssignedAttribute => ... ; type CustomerAssignedAttributeFragment, ; interface MappedAssignedAttribute { additionalData?: Array<{ label: string; value: string }>; value: string[]; }`

### `src/graphql/index.ts`
- `CustomerTypeDetailsFragment`: `(generated)`
- `CustomerTypeFragment`: `(generated)`

## Names that exist and whose declaration changes

### `src/attributes/urls.ts`
- `attributeListUrlWithAttributeTypePreset`: `export const attributeListUrlWithAttributeTypePreset = (attributeType: BuiltInAttributeType) => ... ; type BuiltInAttributeType = | AttributeTypeEnum.PRODUCT_TYPE | AttributeTypeEnum.PAGE_TYPE | AttributeTypeEnum.CUSTOMER_TYPE`

### `src/components/ConditionalFilter/API/FilterAPIProvider.ts`
- `FilterAPIProvider`: `export interface FilterAPIProvider { fetchRightOptions: ( position: string, value: FilterContainer, inputValue: string, after?: string | null, ) => Promise<FilterChoicesPage>; fetchAttributeOptions: ( inputValue: string, after?: string | null, ) => Promise<FilterChoicesPage<LeftOperand>>; }`

### `src/components/ConditionalFilter/UI/types.ts`
- `LeftOperatorOption`: `export type LeftOperatorOption = Option & { type: string; slug?: string; }`

### `src/customers/components/CustomerDetailsPage/CustomerDetailsPage.tsx`
- `default`: `const CustomerDetailsPage = ({ attributeFormRevision = 0, assignReferencesAttributeId, customerId, customer, disabled, errors, fetchMoreReferenceCategories, fetchMoreReferenceCollections, fetchMoreReferencePages, fetchMoreReferenceProducts, fetchReferenceCategories, fetchReferenceCollections, fetchReferencePages, fetchReferenceProducts, initialConstraints, onAssignReferencesClick, onCloseAssignReferences, onFilterChange, saveButtonBar, onSubmit, onDelete, onActivateToggle, onShowMetadata, referenceCategories = [], referenceCollections = [], referencePages = [], referenceProducts = [], }: CustomerDetailsPageProps) => ... ; interface CustomerDetailsPageProps { attributeFormRevision?: number; assignReferencesAttributeId?: string; customerId: string; customer: CustomerDetailsQuery["user"]; disabled: boolean; errors: AccountErrorFragment[]; fetchMoreReferenceCategories?: FetchMoreProps; fetchMoreReferenceCollections?: FetchMoreProps; fetchMoreReferencePages?: FetchMoreProps; fetchMoreReferenceProducts?: FetchMoreProps; fetchReferenceCategories?: (data: string) => void; fetchReferenceCollections?: (data: string) => void; fetchReferencePages?: (data: string) => void; fetchReferenceProducts?: (data: string) => void; initialConstraints?: InitialConstraints & InitialPageConstraints; onAssignReferencesClick?: (attribute: AttributeInput) => void; onCloseAssignReferences?: () => void; onFilterChange?: AssignAttributeValueDialogFilterChangeMap; onSubmit: (data: CustomerDetailsPageSubmitData) => SubmitPromise<AccountErrorFragment[]>; onDelete: () => void; onActivateToggle: () => void; onShowMetadata: () => void; referenceCategories?: ReferenceEntitiesSearch["categories"]; referenceCollections?: ReferenceEntitiesSearch["collections"]; referencePages?: ReferenceEntitiesSearch["pages"]; referenceProducts?: ReferenceEntitiesSearch["products"]; saveButtonBar: ConfirmButtonTransitionState; }`

### `src/customers/components/CustomerOverview/CustomerOverview.tsx`
- `CustomerOverview`: `export const CustomerOverview = ({ customer }: CustomerOverviewProps): JSX.Element => ... ; interface CustomerOverviewProps { customer?: CustomerDetailsQuery["user"] | null; }`

### `src/customers/providers/CustomerDetailsProvider.tsx`
- `CustomerDetailsContext`: `export const CustomerDetailsContext = createContext<CustomerDetailsConsumerProps | null>(null); ; interface CustomerDetailsConsumerProps { customer: CustomerDetailsQuery | null; loading: boolean | null; kpiChannelId: string | undefined; setKpiChannelId: (channelId: string | undefined) => void; kpiChannels: ChannelFromOrder[]; effectiveKpiChannelId: string | undefined; refetch: () => Promise<unknown>; }`

### `src/customers/urls.ts`
- `customerAddUrl`: `export const customerAddUrl = (params?: CustomerCreateUrlQueryParams) => ... ; export type CustomerCreateUrlQueryParams = CustomerCreateUrlCustomerType`

### `src/modeling/components/ModelTypeTabs/ModelTypeTabs.tsx`
- `ModelTypeTabs`: `export const ModelTypeTabs = ({ pageTypes, selectedIds, counts, onTabChange, grouping, rightSlot, pinStorageKey = PINNED_TABS_STORAGE_KEY, testId = "model-type-tabs", testIdPrefix = "model-type-tab", }: ModelTypeTabsProps) => ... ; export interface ModelTypeTabsProps { pageTypes: ModelTypeTabItem[] | undefined; selectedIds: string[]; counts: Record<string, ModelTypeTabCount | undefined>; onTabChange: (ids: string[]) => void; /** * Grouping state owned by the parent so a single source of truth drives both the * tab strip and the parent's count bookkeeping. Falls back to a local hook instance * when rendered standalone (Storybook, tests). * Pass `false` to keep a flat type strip (no name-splitting) and hide grouping settings * — used by customers today, and the hook to turn grouping on later. */ grouping?: ModelTypeTabGrouping | false; /** Optional slot anchored to the right of the strip, sharing the bottom border. */ rightSlot?: ReactNode; /** localStorage key for pinned tabs. Defaults to the models list key. */ pinStorageKey?: string; /** data-test-id on the tablist. */ testId?: string; /** Prefix for per-tab test ids (`{prefix}-{id}`). */ testIdPrefix?: string; } type ModelTypeTabStripItem = { kind: "all"; id: string; name: string } | ModelTabNode; const getStripItemId = (item: ModelTypeTabStripItem): string => { if (item.kind === "all") { return item.id; } return getModelTabNodeId(item); }; const getStripItemSelection = (item: ModelTypeTabStripItem): string[] => { if (item.kind === "all") { return []; } return getModelTabNodeSelection(item); }; const isStripItemActive = (item: ModelTypeTabStripItem, selectedIds: string[]): boolean => { if (item.kind === "all") { return selectedIds.length === 0; } retu ...`

## What the tests look for on the page

Tests of the components in each directory find elements by these test ids (`data-test-id`) and by this
exact visible text. Neither exists in the source yet.

### `src/customerTypes/components/CreateCustomerTypeDialog`
- test ids: `customer-type-name-input`

### `src/customerTypes/components/CustomerTypeAttributes`
- test ids: `customer-attributes-skeleton`

### `src/customerTypes/components/CustomerTypeDetailsPage`
- test ids: `customer-type-default-pill`, `customer-type-details-title-skeleton`, `customer-type-name`, `delete-customer-type`, `set-default-customer-type`, `show-customer-type-metadata`

### `src/customerTypes/components/CustomerTypeMetadataDialog`
- text: "Customer Type Metadata"

### `src/customers/components/CustomerAddresses`
- test ids: `customer-addresses-loading`

### `src/customers/components/CustomerAttributesCard`
- test ids: `change-customer-type`, `change-customer-type-dialog`, `customer-attributes`, `customer-attributes-menu`, `customer-attributes-type`, `customer-type-change-warning`, `customer-type-option-type-1`, `customer-type-option-type-2`, `customer-type-select`, `view-customer-type`
- text: "This type has no attributes"

### `src/customers/components/CustomerDetailsPage`
- test ids: `customer-details`, `customer-details-customer-type-skeleton`, `customer-details-status-skeleton`, `customer-details-title-skeleton`, `customer-type-card-mock`

### `src/customers/components/CustomerListPage`
- test ids: `create-customer-dropdown`, `create-customer-type`

### `src/customers/components/CustomerOrders`
- test ids: `customer-order-status`

## What the tests check to the letter

Behaviour the hidden tests assert exactly, which the description of the feature does not settle.

- The copies of the API's schema kept here describe the API as it is today, without the feature. They are judged as well: they must state what the API gained, exactly as the API's code produces it.
- `src/customerTypes/components/CustomerTypeTabs/CustomerTypeTabs.tsx` exports `CustomerTypeTabs`, and `src/customerTypes/components/CustomerTypeDetails/CustomerTypeDetails.tsx` exports `CustomerTypeDetails` (named exports; the tests mock both by these names).
- `src/customers/hooks/useCustomerDetailsAttributes.ts` exports `useCustomerDetailsAttributes`, which returns `{ attributeRichTextGetters, attributes, attributeValues, fetchAttributeValues, fetchMoreAttributeValues, getSubmitData, handleTypeChange, isDirty, handlers: { fetchMoreReferences, fetchReferences, onAttributeSelectBlur, onChange, onFileChange, onMultiChange, onReferencesReorder, selectAttributeReference, selectAttributeReferenceAdditionalData }, typeAttributesLoading }`; `getSubmitData()` resolves to `{ attributes, attributesWithNewFileValue }`. The customer details page uses it; its test mocks it with that shape.
- The query of customer types the customer's attributes card uses is named `CustomerTypeList` (so its hook is `useCustomerTypeListQuery`; the card's test mocks it).
- When a customer's type is changed to one with different attributes, the attributes card says "This type uses different attributes" and "Values from the previous type stay stored. They'll show again if you switch back."
- When the customer list is filtered to one customer type (`CustomerListPage` props `selectedTypeIds` and `activeCustomerTypeName`), its create button is labelled "Create " and the type's name, for example "Create B2B".
