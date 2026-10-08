use std::collections::BTreeMap;

use crate::framework::{execution, router, Plugin};

pub const TIER_CONTEXT_KEY: &str = "acme.query_budget.tier";

#[derive(Clone, Debug)]
pub struct QueryBudgetConfig {
    pub enabled: bool,
    pub client_tier_header: String,
    pub default_tier: String,
    pub tier_limits: BTreeMap<String, u32>,
    pub mutation_max_cost: u32,
    pub rejection_status: u16,
    pub error_code: String,
    pub error_message: String,
}

#[derive(Clone, Debug)]
pub struct QueryBudget {
    pub configuration: QueryBudgetConfig,
    default_limit: u32,
}

impl Plugin for QueryBudget {
    type Config = QueryBudgetConfig;

    async fn new(configuration: Self::Config) -> Result<Self, String> {
        let _ = configuration;
        todo!("validate and retain the query-budget configuration")
    }

    fn router_service(&self, service: router::BoxService) -> router::BoxService {
        let _ = self;
        service
    }

    fn execution_service(&self, service: execution::BoxService) -> execution::BoxService {
        let _ = self;
        service
    }
}

// Register acme.query_budget here.
