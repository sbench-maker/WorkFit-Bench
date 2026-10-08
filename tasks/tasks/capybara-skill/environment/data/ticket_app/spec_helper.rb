# frozen_string_literal: true

require "capybara/rspec"
require_relative "app"

Capybara.app = TicketApp.new
Capybara.default_driver = :rack_test
Capybara.default_max_wait_time = 2

RSpec.configure do |config|
  config.before do
    Capybara.reset_sessions!
  end
end
