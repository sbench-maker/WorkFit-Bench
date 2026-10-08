declare global {
  namespace Cypress {
    interface Chainable {
      beginCheckout(sku: string, quantity: number, shipping?: 'standard' | 'express', promo?: string): Chainable<void>;
    }
  }
}

Cypress.Commands.add('beginCheckout', (sku, quantity, shipping = 'standard', promo = '') => {
  cy.get('[data-testid="product"]').select(sku);
  cy.get('[data-testid="quantity"]').clear().type(String(quantity));
  cy.get('[data-testid="shipping"]').select(shipping);
  if (promo) cy.get('[data-testid="promo"]').type(promo);
  cy.get('[data-testid="place-order"]').click();
});

export {};
