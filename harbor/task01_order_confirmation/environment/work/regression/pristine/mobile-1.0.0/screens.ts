// What each screen shows, built from Core's answers. All money and status text the app displays is formatted here.

interface Money { amount: number; currency: string }
interface Taxed { gross: Money; net: Money; tax: Money }

const STATUS: Record<string, string> = {
  UNCONFIRMED: "Order received", UNFULFILLED: "Being prepared", PARTIALLY_FULFILLED: "Partly shipped", FULFILLED: "Shipped", CANCELED: "Cancelled",
};

/** Core's Money as text. `amount` is a decimal number in major units; only USD exists today. */
export function money(m: Money): string {
  return (m.amount < 0 ? "-" : "") + "$" + Math.abs(m.amount).toFixed(2);
}

const shown = (price: Taxed, displayGross: boolean) => (displayGross ? price.gross : price.net);

export function productListScreen(data: any) {
  return {
    title: "Shop",
    products: data.products.edges.flatMap((e: any) => e.node.variants.map((v: any) => ({
      variantId: v.id, sku: v.sku, name: e.node.name, price: money(v.pricing.price.net),
    }))),
  };
}

function summary(gross: boolean, lines: any[], subtotal: Taxed, shipping: Taxed, total: Taxed) {
  return {
    lines: lines.map((l) => ({ name: l.productName ?? l.variant.product.name, quantity: l.quantity, total: money(shown(l.totalPrice, gross)) })),
    subtotal: money(shown(subtotal, gross)),
    shipping: money(shipping.gross),
    tax: money(total.tax),
    total: money(total.gross),
  };
}

export function cartScreen(checkout: any) {
  return { title: "Your cart", ...summary(checkout.displayGrossPrices, checkout.lines, checkout.subtotalPrice, checkout.shippingPrice, checkout.totalPrice) };
}

export function orderScreen(order: any) {
  return {
    title: `Order #${order.number}`,
    status: STATUS[order.status] ?? order.status,
    paid: order.chargeStatus === "FULL",
    ...summary(order.displayGrossPrices, order.lines, order.subtotal, order.shippingPrice, order.total),
  };
}
