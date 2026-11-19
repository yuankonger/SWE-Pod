// Every GraphQL operation the app sends to Core, by name. A released build carries its own copy of this file:
// once a version is on people's phones, the operations it sends can no longer be changed.
const MONEY = "{ amount currency }";
const TAXED = `{ gross ${MONEY} net ${MONEY} tax ${MONEY} }`;
const CHECKOUT = `{ id displayGrossPrices lines { quantity variant { id sku name product { name } } totalPrice ${TAXED} }
  shippingMethods { id name price ${MONEY} } subtotalPrice ${TAXED} shippingPrice ${TAXED} totalPrice ${TAXED} }`;
const ORDER = `{ id number status chargeStatus displayGrossPrices lines { productName variantName quantity totalPrice ${TAXED} }
  subtotal ${TAXED} shippingPrice ${TAXED} total ${TAXED} }`;
const ERRORS = "errors { field message code }";

export const OPERATIONS = {
  ProductList: `query ProductList { products(first: 50, channel: "default-channel") { edges { node { id name variants { id sku name pricing { price ${TAXED} } } } } } }`,
  CheckoutCreate: `mutation CheckoutCreate($email: String!, $lines: [CheckoutLineInput!]!) {
    checkoutCreate(input: { channel: "default-channel", email: $email, lines: $lines }) { checkout ${CHECKOUT} ${ERRORS} } }`,
  CheckoutShippingAddressUpdate: `mutation CheckoutShippingAddressUpdate($id: ID!, $address: AddressInput!) {
    checkoutShippingAddressUpdate(id: $id, shippingAddress: $address) { checkout ${CHECKOUT} ${ERRORS} } }`,
  CheckoutDeliveryMethodUpdate: `mutation CheckoutDeliveryMethodUpdate($id: ID!, $method: ID) {
    checkoutDeliveryMethodUpdate(id: $id, deliveryMethodId: $method) { checkout ${CHECKOUT} ${ERRORS} } }`,
  Pay: `mutation Pay($id: ID!, $data: JSON, $key: String) {
    transactionInitialize(id: $id, idempotencyKey: $key, paymentGateway: { id: "seedco.payments", data: $data }) {
      transactionEvent { type message } ${ERRORS} } }`,
  CheckoutComplete: `mutation CheckoutComplete($id: ID!) { checkoutComplete(id: $id) { order ${ORDER} ${ERRORS} } }`,
  OrderStatus: `query OrderStatus($id: ID!) { order(id: $id) ${ORDER} }`,
} as const;
export type OperationName = keyof typeof OPERATIONS;
