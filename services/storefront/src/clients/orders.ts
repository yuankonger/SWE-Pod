// The Orders API as Storefront uses it. Shapes follow pinned/orders-api.yaml.
import { call } from "./http.ts";

export interface Product { sku: string; name: string; unit_price: number }
export interface CartItem extends Product { qty: number }
export interface Cart { customer_id: string; items: CartItem[]; subtotal: number }
export interface OrderLine { sku: string; name: string; qty: number; unit_price: number }
export interface Order {
  order_id: string; customer_id: string; status: string; lines: OrderLine[];
  subtotal: number; tax: number; total: number; created_at?: string;
}
export interface CheckoutDetails { email: string; postal_code: number; payment_method?: string }

export interface OrdersClient {
  catalog(): Promise<Product[]>;
  cart(customerId: string): Promise<Cart>;
  setCartItem(customerId: string, sku: string, qty: number): Promise<Cart>;
  checkoutCart(customerId: string, details: CheckoutDetails, idempotencyKey?: string): Promise<Order>;
  place(body: unknown): Promise<Order>;
  get(orderId: string): Promise<Order>;
  list(customerId: string): Promise<Order[]>;
  cancel(orderId: string): Promise<Order>;
}

const PAGE = 50;

export function ordersClient(base: string): OrdersClient {
  const id = encodeURIComponent;
  return {
    catalog: async () => (await call(`${base}/catalog`)).products,
    cart: (customerId) => call(`${base}/carts/${id(customerId)}`),
    setCartItem: (customerId, sku, qty) => call(`${base}/carts/${id(customerId)}/items/${id(sku)}`, "PUT", { qty }),
    checkoutCart: (customerId, details, key) =>
      call(`${base}/carts/${id(customerId)}/checkout`, "POST", details, key ? { "Idempotency-Key": key } : {}),
    place: (body) => call(`${base}/orders`, "POST", body),
    get: (orderId) => call(`${base}/orders/${id(orderId)}`),
    // Orders returns a page at a time; the account page shows every order, so follow `next` to the end.
    list: async (customerId) => {
      const all: Order[] = [];
      let after: string | null = null;
      do {
        const page: { orders: Order[]; next?: string | null } = await call(
          `${base}/orders?customer_id=${id(customerId)}&limit=${PAGE}` + (after ? `&after=${id(after)}` : ""));
        all.push(...page.orders);
        after = page.next ?? null;
      } while (after);
      return all;
    },
    cancel: (orderId) => call(`${base}/orders/${id(orderId)}/cancel`, "POST"),
  };
}
