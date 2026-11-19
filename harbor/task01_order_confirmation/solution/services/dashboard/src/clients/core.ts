// The Core API as the Dashboard uses it: staff operations against pinned/schema.graphql, with the signed-in
// member's token. Core decides what each member may do; a refusal comes back as PermissionDenied.
import { call } from "./http.ts";

export interface Money { amount: number; currency: string }
export interface TaxedMoney { gross: Money; net: Money; tax: Money }
export interface OrderSummary { id: string; number: string; created: string; status: string; chargeStatus: string; userEmail: string | null; total: TaxedMoney }
export interface OrderLine { id: string; productName: string; productSku: string | null; quantity: number; quantityFulfilled: number; totalPrice: TaxedMoney }
export interface TransactionEvent { type: string | null; amount: Money; message: string; createdAt: string }
export interface Transaction { id: string; name: string; pspReference: string; chargedAmount: Money; refundedAmount: Money; actions: string[]; events: TransactionEvent[] }
export interface Order extends OrderSummary {
  origin: string; lines: OrderLine[]; subtotal: TaxedMoney; shippingPrice: TaxedMoney; totalCharged: Money; totalRefunded: Money;
  transactions: Transaction[]; metadata: { key: string; value: string }[];
  shippingAddress: { firstName: string; lastName: string; streetAddress1: string; city: string; postalCode: string; countryArea: string } | null;
}
export interface App {
  identifier: string; name: string; version: string; isActive: boolean; permissions: { code: string }[];
  webhooks: { name: string; targetUrl: string; syncEvents: { eventType: string }[]; asyncEvents: { eventType: string }[]; subscriptionQuery: string }[];
}
export interface ApiError { field: string | null; message: string | null; code: string }

/** Core refused the operation: either the member lacks a permission, or the mutation returned errors. */
export class Refused extends Error {
  permission: boolean;
  constructor(message: string, permission = false) {
    super(message);
    this.permission = permission;
  }
}

export interface CoreClient {
  signIn(email: string, password: string): Promise<string | null>;
  orders(token: string, customer?: string): Promise<{ orders: OrderSummary[]; total: number }>;
  order(token: string, id: string): Promise<Order | null>;
  fulfill(token: string, orderId: string, lines: { orderLineId: string; quantity: number }[]): Promise<void>;
  cancel(token: string, orderId: string): Promise<void>;
  confirm(token: string, orderId: string): Promise<void>;
  refund(token: string, transactionId: string, amount?: number): Promise<void>;
  apps(token: string): Promise<App[]>;
}

const MONEY = "{ amount currency }";
const TAXED = `{ gross ${MONEY} net ${MONEY} tax ${MONEY} }`;
const SUMMARY = `id number created status chargeStatus userEmail total ${TAXED}`;

export function coreClient(url: string): CoreClient {
  async function gql<T = any>(token: string | null, query: string, variables: Record<string, unknown> = {}): Promise<T> {
    const res = await call<{ data?: T; errors?: { message: string; extensions?: { exception?: { code?: string } } }[] }>(
      url, "POST", { query, variables }, token ? { Authorization: `Bearer ${token}` } : {});
    if (res.errors?.length) {
      const denied = res.errors.some((e) => e.extensions?.exception?.code === "PermissionDenied");
      throw denied ? new Refused(res.errors[0].message, true) : new Error("core: " + res.errors.map((e) => e.message).join("; "));
    }
    return res.data as T;
  }
  async function mutate(token: string, name: string, query: string, variables: Record<string, unknown>) {
    const errors: ApiError[] = (await gql(token, query, variables))[name].errors;
    if (errors.length) throw new Refused(errors.map((e) => e.message ?? e.code).join("; "));
  }
  return {
    signIn: async (email, password) => (await gql(null, `mutation($email: String!, $password: String!) {
      tokenCreate(email: $email, password: $password) { token errors { code } } }`, { email, password })).tokenCreate.token,
    orders: async (token, customer) => {
      const data = await gql(token, `query($filter: OrderFilterInput) { orders(first: 50, filter: $filter) { totalCount edges { node { ${SUMMARY} } } } }`,
        { filter: customer ? { customer } : null });
      return { orders: data.orders.edges.map((e: any) => e.node), total: data.orders.totalCount };
    },
    order: async (token, id) => (await gql(token, `query($id: ID!) { order(id: $id) { ${SUMMARY} origin
      lines { id productName productSku quantity quantityFulfilled totalPrice ${TAXED} }
      subtotal ${TAXED} shippingPrice ${TAXED} totalCharged ${MONEY} totalRefunded ${MONEY} metadata { key value }
      shippingAddress { firstName lastName streetAddress1 city postalCode countryArea }
      transactions { id name pspReference chargedAmount ${MONEY} refundedAmount ${MONEY} actions events { type amount ${MONEY} message createdAt } } } }`, { id })).order,
    fulfill: (token, orderId, lines) => mutate(token, "orderFulfill",
      `mutation($order: ID!, $lines: [OrderFulfillLineInput!]!) { orderFulfill(order: $order, input: { lines: $lines }) { errors { field message code } } }`, { order: orderId, lines }),
    confirm: (token, orderId) => mutate(token, "orderConfirm", `mutation($id: ID!) { orderConfirm(id: $id) { errors { field message code } } }`, { id: orderId }),
    cancel: (token, orderId) => mutate(token, "orderCancel", `mutation($id: ID!) { orderCancel(id: $id) { errors { field message code } } }`, { id: orderId }),
    refund: (token, transactionId, amount) => mutate(token, "transactionRequestAction",
      `mutation($id: ID!, $amount: PositiveDecimal) { transactionRequestAction(id: $id, actionType: REFUND, amount: $amount) { errors { field message code } } }`,
      { id: transactionId, amount: amount ?? null }),
    apps: async (token) => (await gql(token, `{ apps { identifier name version isActive permissions { code }
      webhooks { name targetUrl syncEvents { eventType } asyncEvents { eventType } subscriptionQuery } } }`)).apps,
  };
}
