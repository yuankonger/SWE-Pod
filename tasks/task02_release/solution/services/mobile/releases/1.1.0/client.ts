// The app's journeys against Core: browse, buy, look at the order. `send` posts one named operation.
import { OPERATIONS, type OperationName } from "./operations.ts";
import { cartScreen, orderScreen, productListScreen } from "./screens.ts";

export type Send = (query: string, variables: Record<string, unknown>) => Promise<{ data?: any; errors?: { message: string }[] }>;

export interface Purchase {
  email: string;
  items: Record<string, number>;            // sku -> quantity
  address: { firstName: string; lastName: string; streetAddress1: string; city: string; postalCode: string; country: string; countryArea: string };
  paymentMethod: string;
}

/** Something the app shows the customer instead of a result. */
export class AppError extends Error {}

export function httpSend(coreUrl: string): Send {
  return async (query, variables) => {
    const res = await fetch(coreUrl, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ query, variables }),
      signal: AbortSignal.timeout(30_000) });
    return res.json();
  };
}

export function createApp(send: Send, operations: Record<OperationName, string> = OPERATIONS) {
  async function run(name: OperationName, variables: Record<string, unknown> = {}) {
    const res = await send(operations[name], variables);
    if (res.errors?.length || !res.data) throw new AppError(`${name}: ${res.errors?.[0]?.message ?? "no data"}`);
    return res.data;
  }
  /** Runs a mutation and returns its payload, or throws the first error Core's mutation reported. */
  async function mutate(name: OperationName, field: string, variables: Record<string, unknown>) {
    const payload = (await run(name, variables))[field];
    if (payload.errors.length) throw new AppError(`${name}: ${payload.errors[0].message ?? payload.errors[0].code}`);
    return payload;
  }

  return {
    products: async () => productListScreen(await run("ProductList")),
    order: async (id: string) => orderScreen((await run("OrderStatus", { id })).order),
    /** Buys the items and returns the screens the customer saw on the way. */
    async purchase(p: Purchase, idempotencyKey: string) {
      const shop = productListScreen(await run("ProductList"));
      const lines = Object.entries(p.items).map(([sku, quantity]) => {
        const product = shop.products.find((x: any) => x.sku === sku);
        if (!product) throw new AppError(`This item is no longer available (${sku}).`);
        return { variantId: product.variantId, quantity };
      });
      const created = await mutate("CheckoutCreate", "checkoutCreate", { email: p.email, lines });
      const addressed = await mutate("CheckoutShippingAddressUpdate", "checkoutShippingAddressUpdate", { id: created.checkout.id, address: p.address });
      const method = addressed.checkout.shippingMethods[0];
      if (!method) throw new AppError("We cannot ship to that address.");
      const ready = await mutate("CheckoutDeliveryMethodUpdate", "checkoutDeliveryMethodUpdate", { id: created.checkout.id, method: method.id });
      const cart = cartScreen(ready.checkout);
      const payment = (await mutate("Pay", "transactionInitialize", { id: created.checkout.id, data: { paymentMethod: p.paymentMethod }, key: idempotencyKey })).transactionEvent;
      if (payment.type !== "CHARGE_SUCCESS") throw new AppError(`Your payment did not go through (${payment.message || "try another card"}).`);
      const done = await mutate("CheckoutComplete", "checkoutComplete", { id: created.checkout.id });
      return { shop, cart, order: orderScreen(done.order), orderId: done.order.id as string };
    },
  };
}
