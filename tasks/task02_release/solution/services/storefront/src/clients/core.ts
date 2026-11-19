// The Core API as Storefront uses it: GraphQL operations against pinned/schema.graphql.
// Each operation asks only for the fields the shop shows.
import { call } from "./http.ts";

export interface Money { amount: number; currency: string }
export interface TaxedMoney { gross: Money; net: Money; tax: Money }
export interface Variant { id: string; sku: string | null; name: string; pricing: { price: TaxedMoney } }
export interface Product { id: string; name: string; variants: Variant[] }
export interface CheckoutLine { id: string; quantity: number; variant: { id: string; sku: string | null; name: string; product: { name: string } }; unitPrice: TaxedMoney; totalPrice: TaxedMoney }
export interface Checkout {
  id: string; email: string | null; displayGrossPrices: boolean; chargeStatus: string; lines: CheckoutLine[];
  shippingMethods: { id: string; name: string; price: Money }[];
  subtotalPrice: TaxedMoney; shippingPrice: TaxedMoney; totalPrice: TaxedMoney;
  availablePaymentGateways: { id: string; name: string }[];
}
export interface OrderLine { productName: string; variantName: string; quantity: number; unitPrice: TaxedMoney; totalPrice: TaxedMoney }
export interface Order {
  id: string; number: string; status: string; chargeStatus: string; userEmail: string | null; displayGrossPrices: boolean;
  created: string; lines: OrderLine[]; subtotal: TaxedMoney; shippingPrice: TaxedMoney; total: TaxedMoney; totalRefunded: Money;
}
export interface Address { firstName: string; lastName: string; streetAddress1: string; city: string; postalCode: string; country: string; countryArea: string }
export interface ApiError { field: string | null; message: string | null; code: string }
export interface PaymentResult { type: string | null; message: string }

/** A mutation Core refused. `errors` is what the mutation returned. */
export class CoreError extends Error {
  errors: ApiError[];
  constructor(errors: ApiError[]) {
    super(errors.map((e) => e.message ?? e.code).join("; "));
    this.errors = errors;
  }
}

export interface CoreClient {
  products(search?: string): Promise<Product[]>;
  checkout(id: string): Promise<Checkout | null>;
  checkoutCreate(lines: { variantId: string; quantity: number }[]): Promise<Checkout>;
  linesAdd(id: string, variantId: string, quantity: number): Promise<Checkout>;
  linesUpdate(id: string, variantId: string, quantity: number): Promise<Checkout>;
  setEmail(id: string, email: string): Promise<Checkout>;
  setShippingAddress(id: string, address: Address): Promise<Checkout>;
  setDeliveryMethod(id: string, methodId: string): Promise<Checkout>;
  pay(id: string, gateway: string, paymentMethod: string, idempotencyKey: string): Promise<PaymentResult>;
  complete(id: string): Promise<Order>;
  order(id: string): Promise<Order | null>;
}

const MONEY = "{ amount currency }";
const TAXED = `{ gross ${MONEY} net ${MONEY} tax ${MONEY} }`;
const CHECKOUT = `{ id email displayGrossPrices chargeStatus
  lines { id quantity variant { id sku name product { name } } unitPrice ${TAXED} totalPrice ${TAXED} }
  shippingMethods { id name price ${MONEY} }
  subtotalPrice ${TAXED} shippingPrice ${TAXED} totalPrice ${TAXED} availablePaymentGateways { id name } }`;
const ORDER = `{ id number status chargeStatus userEmail displayGrossPrices created
  lines { productName variantName quantity unitPrice ${TAXED} totalPrice ${TAXED} }
  subtotal ${TAXED} shippingPrice ${TAXED} total ${TAXED} totalRefunded ${MONEY} }`;

export function coreClient(url: string, channel = "default-channel"): CoreClient {
  async function gql<T = any>(query: string, variables: Record<string, unknown> = {}): Promise<T> {
    const res = await call<{ data?: T; errors?: { message: string }[] }>(url, "POST", { query, variables });
    if (res.errors?.length) throw new Error("core: " + res.errors.map((e) => e.message).join("; "));
    return res.data as T;
  }
  /** Runs a checkout mutation and returns its checkout, or throws what the mutation refused. */
  async function change(name: string, signature: string, args: string, variables: Record<string, unknown>): Promise<Checkout> {
    const data = await gql(`mutation(${signature}) { ${name}(${args}) { checkout ${CHECKOUT} errors { field message code } } }`, variables);
    if (data[name].errors.length) throw new CoreError(data[name].errors);
    return data[name].checkout;
  }
  return {
    products: async (search) => (await gql(`query($channel: String, $filter: ProductFilterInput) { products(first: 100, channel: $channel, filter: $filter) {
      edges { node { id name variants { id sku name pricing { price ${TAXED} } } } } } }`, { channel, filter: search ? { search } : null })).products.edges.map((e: any) => e.node),
    checkout: async (id) => (await gql(`query($id: ID!) { checkout(id: $id) ${CHECKOUT} }`, { id })).checkout,
    checkoutCreate: (lines) => change("checkoutCreate", "$input: CheckoutCreateInput!", "input: $input", { input: { channel, lines } }),
    linesAdd: (id, variantId, quantity) => change("checkoutLinesAdd", "$id: ID!, $lines: [CheckoutLineInput!]!", "id: $id, lines: $lines",
      { id, lines: [{ variantId, quantity }] }),
    linesUpdate: (id, variantId, quantity) => change("checkoutLinesUpdate", "$id: ID!, $lines: [CheckoutLineUpdateInput!]!", "id: $id, lines: $lines",
      { id, lines: [{ variantId, quantity }] }),
    setEmail: (id, email) => change("checkoutEmailUpdate", "$id: ID!, $email: String!", "id: $id, email: $email", { id, email }),
    setShippingAddress: (id, address) => change("checkoutShippingAddressUpdate", "$id: ID!, $address: AddressInput!",
      "id: $id, shippingAddress: $address", { id, address }),
    setDeliveryMethod: (id, methodId) => change("checkoutDeliveryMethodUpdate", "$id: ID!, $method: ID", "id: $id, deliveryMethodId: $method",
      { id, method: methodId }),
    pay: async (id, gateway, paymentMethod, idempotencyKey) => {
      const data = await gql(`mutation($id: ID!, $gateway: String!, $data: JSON, $key: String) {
        transactionInitialize(id: $id, idempotencyKey: $key, paymentGateway: { id: $gateway, data: $data }) {
          transactionEvent { type message } errors { field message code } } }`, { id, gateway, data: { paymentMethod }, key: idempotencyKey });
      if (data.transactionInitialize.errors.length) throw new CoreError(data.transactionInitialize.errors);
      return data.transactionInitialize.transactionEvent;
    },
    complete: async (id) => {
      const data = await gql(`mutation($id: ID!) { checkoutComplete(id: $id) { order ${ORDER} errors { field message code } } }`, { id });
      if (data.checkoutComplete.errors.length) throw new CoreError(data.checkoutComplete.errors);
      return data.checkoutComplete.order;
    },
    order: async (id) => (await gql(`query($id: ID!) { order(id: $id) ${ORDER} }`, { id })).order,
  };
}
