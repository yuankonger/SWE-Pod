// The Subscriptions app's API as Storefront uses it. Shapes follow pinned/subscriptions-api.yaml.
import { call } from "./http.ts";
import type { Money } from "./core.ts";

export interface Plan { sku: string; name: string; unit_price: Money }
export interface Subscription {
  subscription_id: string; email: string; sku: string; name: string; qty: number; unit_price: Money; status: string;
  current_period_start: string; current_period_end: string;
  pending_sku?: string | null; pending_name?: string | null; cancel_at_period_end?: boolean;
}

export interface SubscriptionsClient {
  plans(): Promise<Plan[]>;
  forEmail(email: string): Promise<Subscription[]>;
  changePlan(subscriptionId: string, sku: string): Promise<Subscription>;
  cancel(subscriptionId: string): Promise<Subscription>;
}

export function subscriptionsClient(base: string): SubscriptionsClient {
  const id = encodeURIComponent;
  return {
    plans: async () => (await call(`${base}/api/plans`)).plans,
    forEmail: async (email) => (await call(`${base}/api/subscriptions?email=${id(email)}`)).subscriptions,
    changePlan: (subscriptionId, sku) => call(`${base}/api/subscriptions/${id(subscriptionId)}/plan`, "POST", { sku }),
    cancel: (subscriptionId) => call(`${base}/api/subscriptions/${id(subscriptionId)}/cancel`, "POST"),
  };
}
