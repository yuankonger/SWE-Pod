// The Billing API as Storefront uses it. Shapes follow pinned/billing-api.yaml.
import { call } from "./http.ts";
import type { Money } from "./orders.ts";

export interface Invoice { invoice_id: string; order_id: string; total: Money; status: string; reason?: string }
export interface Plan { sku: string; name: string; unit_price: Money }
export interface Subscription {
  subscription_id: string; order_id: string; customer_id: string; sku: string; name: string; qty: number;
  unit_price: Money; status: string; current_period_start: string; current_period_end: string;
  pending_sku?: string | null; pending_name?: string | null; cancel_at_period_end?: boolean;
}

export interface BillingClient {
  invoices(orderId: string): Promise<Invoice[]>;
  plans(): Promise<Plan[]>;
  subscriptions(customerId: string): Promise<Subscription[]>;
  changePlan(subscriptionId: string, sku: string): Promise<Subscription>;
  cancelSubscription(subscriptionId: string): Promise<Subscription>;
}

export function billingClient(base: string): BillingClient {
  const id = encodeURIComponent;
  return {
    invoices: async (orderId) => (await call(`${base}/invoices?order_id=${id(orderId)}`)).invoices,
    plans: async () => (await call(`${base}/plans`)).plans,
    subscriptions: async (customerId) => (await call(`${base}/subscriptions?customer_id=${id(customerId)}`)).subscriptions,
    changePlan: (subscriptionId, sku) => call(`${base}/subscriptions/${id(subscriptionId)}/plan`, "POST", { sku }),
    cancelSubscription: (subscriptionId) => call(`${base}/subscriptions/${id(subscriptionId)}/cancel`, "POST"),
  };
}
