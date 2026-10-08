# frozen_string_literal: true

require "cgi"
require "json"
require "rack"

class TicketApp
  EVENTS_PATH = ENV.fetch("TICKET_EVENTS_PATH", File.expand_path("events.json", __dir__))

  def initialize
    @events = JSON.parse(File.read(EVENTS_PATH))
  end

  def call(env)
    request = Rack::Request.new(env)
    case [request.request_method, request.path_info]
    when ["GET", "/events"]
      ok(events_page(request.params["query"].to_s))
    when ["GET", "/checkout"]
      event = event_by_id(request.params["event_id"])
      event ? ok(checkout_page(event)) : not_found
    when ["POST", "/checkout/quote"]
      quote(request)
    when ["POST", "/purchase"]
      purchase(request)
    else
      if request.get? && request.path_info.match?(%r{\A/orders/EVT-\d{3}\z})
        order_confirmation(request)
      else
        not_found
      end
    end
  end

  private

  def event_by_id(event_id)
    @events.find { |event| event["id"] == event_id }
  end

  def sold_out?(event)
    event["status"] == "sold_out"
  end

  def events_page(query)
    matches = if query.strip.empty?
                @events.first(12)
              else
                needle = query.downcase
                @events.select do |event|
                  [event["title"], event["venue"], event["city"]].any? { |value| value.downcase.include?(needle) }
                end
              end
    cards = matches.map do |event|
      action = if sold_out?(event)
                 '<p class="sold-out">Sold out</p><button type="button" disabled>Sold out</button>'
               else
                 <<~HTML
                   <form action="/checkout" method="get">
                     <input type="hidden" name="event_id" value="#{h(event["id"])}">
                     <button type="submit">Choose tickets</button>
                   </form>
                 HTML
               end
      <<~HTML
        <article class="event-card" data-event-id="#{h(event["id"])}">
          <h2>#{h(event["title"])}</h2>
          <p class="venue">#{h(event["venue"])}</p>
          <p>#{h(event["city"])} · #{h(event["date"])}</p>
          <p class="price">$#{money(event["price"])}</p>
          #{action}
        </article>
      HTML
    end.join
    layout("Events", <<~HTML)
      <h1>Find an event</h1>
      <form action="/events" method="get" id="event-search">
        <label for="query">Find events</label>
        <input id="query" name="query" value="#{h(query)}">
        <button type="submit">Search</button>
      </form>
      <section id="search-results">#{cards}</section>
    HTML
  end

  def checkout_page(event, values = {}, message = nil, valid_promo: false)
    quantity = [[values.fetch("quantity", "1").to_i, 1].max, 4].min
    attendee = values.fetch("attendee_name", "")
    email = values.fetch("email", "")
    promo = values.fetch("promo", "")
    discount = valid_promo ? 5.0 : 0.0
    total = event["price"].to_f * quantity - discount
    feedback = message ? %(<p class="promo-message">#{h(message)}</p>) : ""
    layout("Checkout", <<~HTML)
      <h1>Checkout</h1>
      <section class="selected-event">
        <h2>#{h(event["title"])}</h2>
        <p>#{h(event["venue"])}</p>
      </section>
      #{feedback}
      <form action="/checkout/quote" method="post" id="checkout-form">
        <input type="hidden" name="event_id" value="#{h(event["id"])}">
        <label for="quantity">Tickets</label>
        <select id="quantity" name="quantity">
          #{(1..4).map { |number| %(<option#{" selected" if number == quantity}>#{number}</option>) }.join}
        </select>
        <label for="attendee_name">Attendee name</label>
        <input id="attendee_name" name="attendee_name" value="#{h(attendee)}">
        <label for="email">Email</label>
        <input id="email" name="email" type="email" value="#{h(email)}">
        <label for="promo">Promo code</label>
        <input id="promo" name="promo" value="#{h(promo)}">
        <button type="submit">Apply promo</button>
      </form>
      <p class="total">Total: $#{money(total)}</p>
      <form action="/purchase" method="post" id="purchase-form">
        <input type="hidden" name="event_id" value="#{h(event["id"])}">
        <input type="hidden" name="quantity" value="#{quantity}">
        <input type="hidden" name="attendee_name" value="#{h(attendee)}">
        <input type="hidden" name="email" value="#{h(email)}">
        <input type="hidden" name="promo" value="#{h(valid_promo ? promo : "")}">
        <button type="submit">Place order</button>
      </form>
    HTML
  end

  def quote(request)
    event = event_by_id(request.params["event_id"])
    return not_found unless event

    promo = request.params["promo"].to_s.strip.upcase
    valid_promo = promo == "NIGHT5"
    message = valid_promo ? "Promo NIGHT5 applied" : "Promo code isn't valid"
    ok(checkout_page(event, request.params, message, valid_promo: valid_promo))
  end

  def purchase(request)
    event = event_by_id(request.params["event_id"])
    return not_found unless event
    return response(409, layout("Unavailable", "<h1>Tickets unavailable</h1>")) if sold_out?(event)

    attendee = request.params["attendee_name"].to_s.strip
    email = request.params["email"].to_s.strip
    return response(422, layout("Missing details", "<h1>Enter attendee details</h1>")) if attendee.empty? || email.empty?

    quantity = [[request.params["quantity"].to_i, 1].max, 4].min
    discount = request.params["promo"].to_s.upcase == "NIGHT5" ? 5.0 : 0.0
    total = event["price"].to_f * quantity - discount
    query = Rack::Utils.build_query("quantity" => quantity, "total" => money(total))
    [303, { "location" => "/orders/#{event["id"]}?#{query}", "content-type" => "text/html; charset=utf-8" }, [""]]
  end

  def order_confirmation(request)
    event_id = request.path_info.split("/").last
    event = event_by_id(event_id)
    return not_found unless event

    quantity = request.params["quantity"].to_i
    total = request.params["total"].to_s
    ok(layout("Order confirmed", <<~HTML))
      <h1>Order confirmed</h1>
      <p class="confirmation-event">#{h(event["title"])} at #{h(event["venue"])}</p>
      <p class="confirmation-quantity">#{quantity} tickets</p>
      <p class="confirmation-total">Total paid: $#{h(total)}</p>
    HTML
  end

  def layout(title, body)
    <<~HTML
      <!doctype html>
      <html lang="en"><head><meta charset="utf-8"><title>#{h(title)}</title></head>
      <body><main>#{body}</main></body></html>
    HTML
  end

  def h(value)
    CGI.escapeHTML(value.to_s)
  end

  def money(value)
    format("%.2f", value)
  end

  def ok(body)
    response(200, body)
  end

  def not_found
    response(404, layout("Not found", "<h1>Not found</h1>"))
  end

  def response(status, body)
    [status, { "content-type" => "text/html; charset=utf-8" }, [body]]
  end
end
