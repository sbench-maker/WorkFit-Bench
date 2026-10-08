describe('checkout regression', () => {
  beforeEach(() => {
    cy.visit('/checkout');
  });

  it('quotes a standard-shipping order and confirms the request payload', () => {
    cy.intercept('POST', '/api/quote').as('quote');
    cy.beginCheckout('P-001', 2);
    cy.wait('@quote').its('request.body').should('deep.equal', {
      sku: 'P-001', quantity: 2, shipping: 'standard', promo: '',
    });
    cy.get('[data-testid="subtotal"]').should('have.text', '$50.00');
    cy.get('[data-testid="discount"]').should('have.text', '$0.00');
    cy.get('[data-testid="shipping-cost"]').should('have.text', '$5.00');
    cy.get('[data-testid="total"]').should('have.text', '$55.00');
    cy.get('[data-testid="confirmation"]').should('be.visible');
  });

  it('applies SAVE10 case-insensitively and preserves cent rounding', () => {
    cy.beginCheckout('P-001', 3, 'standard', 'save10');
    cy.get('[data-testid="subtotal"]').should('have.text', '$75.00');
    cy.get('[data-testid="discount"]').should('have.text', '$7.50');
    cy.get('[data-testid="shipping-cost"]').should('have.text', '$5.00');
    cy.get('[data-testid="total"]').should('have.text', '$72.50');
  });

  it('charges express shipping and grants standard free-shipping at the threshold', () => {
    cy.beginCheckout('P-042', 2, 'express');
    cy.get('[data-testid="total"]').should('have.text', '$95.00');
    cy.reload();
    cy.beginCheckout('P-001', 4, 'standard');
    cy.get('[data-testid="shipping-cost"]').should('have.text', '$0.00');
    cy.get('[data-testid="total"]').should('have.text', '$100.00');
  });

  it('blocks an out-of-stock product before a quote is requested', () => {
    cy.intercept('POST', '/api/quote').as('quote');
    cy.get('[data-testid="product"]').select('P-200');
    cy.get('[data-testid="stock-warning"]').should('be.visible');
    cy.get('[data-testid="place-order"]').should('be.disabled');
    cy.get('@quote.all').should('have.length', 0);
  });

  it('shows a retry message when the pricing service fails', () => {
    cy.intercept('POST', '/api/quote', {
      statusCode: 503,
      body: { error: 'pricing unavailable' },
    });
    cy.beginCheckout('P-001', 1);
    cy.get('[data-testid="quote-error"]').should('contain.text', 'Unable to price order');
    cy.get('[data-testid="confirmation"]').should('not.be.visible');
  });

  it('exposes the receipt as a new-tab link after checkout', () => {
    cy.beginCheckout('P-001', 1);
    cy.get('[data-testid="receipt-link"]')
      .should('have.attr', 'target', '_blank')
      .invoke('removeAttr', 'target')
      .click();
    cy.url().should('include', '/receipt?order=ORD-');
    cy.get('h1').should('have.text', 'Receipt');
  });

  it('does not submit a zero quantity', () => {
    cy.get('[data-testid="quantity"]').clear().type('0');
    cy.get('[data-testid="place-order"]').click();
    cy.get('[data-testid="quantity"]:invalid').should('exist');
    cy.get('[data-testid="confirmation"]').should('not.be.visible');
  });
});
