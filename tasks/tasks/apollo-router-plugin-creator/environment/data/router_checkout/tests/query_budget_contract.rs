use std::collections::BTreeMap;

use acme_router_fixture::framework::{
    block_on, execution, router, Context, OperationKind, Plugin, QueryPlan,
};
use acme_router_fixture::plugins::query_budget::{
    QueryBudget, QueryBudgetConfig, TIER_CONTEXT_KEY,
};

fn config(enabled: bool) -> QueryBudgetConfig {
    QueryBudgetConfig {
        enabled,
        client_tier_header: "x-client-tier".to_string(),
        default_tier: "standard".to_string(),
        tier_limits: BTreeMap::from([
            ("standard".to_string(), 80),
            ("partner".to_string(), 160),
            ("internal".to_string(), 300),
        ]),
        mutation_max_cost: 60,
        rejection_status: 200,
        error_code: "QUERY_COST_EXCEEDED".to_string(),
        error_message: "Query cost exceeds the permitted budget".to_string(),
    }
}

fn route_context(plugin: &QueryBudget, header_name: &str, header_value: &str) -> Context {
    let mut request = router::Request::default();
    if header_name != "-" {
        request = request.with_header(header_name, header_value);
    }
    plugin.router_service(router::passthrough())(request).context
}

#[test]
fn generated_policy_cases_hold() {
    for (line_number, line) in include_str!("../fixtures/policy_cases.csv")
        .lines()
        .enumerate()
        .skip(1)
    {
        let cells: Vec<&str> = line.split(',').collect();
        assert_eq!(cells.len(), 12, "bad fixture line {}", line_number + 1);
        let enabled = cells[1] == "true";
        let plugin = block_on(QueryBudget::new(config(enabled))).unwrap();
        let context = route_context(&plugin, cells[2], cells[3]);
        let expected_tier = cells[6];
        if enabled {
            assert_eq!(context.get(TIER_CONTEXT_KEY), Some(expected_tier));
        } else {
            assert_eq!(context.get(TIER_CONTEXT_KEY), None);
        }

        let operation_kind = if cells[4] == "mutation" {
            OperationKind::Mutation
        } else {
            OperationKind::Query
        };
        let cost: u32 = cells[5].parse().unwrap();
        let response = plugin.execution_service(execution::passthrough())(execution::Request {
            query_plan: QueryPlan {
                estimated_cost: cost,
                operation_kind,
            },
            context,
        });
        let expected_allowed = cells[8] == "true";
        assert_eq!(response.executed, expected_allowed, "case {}", cells[0]);
        assert_eq!(response.status_code, cells[9].parse::<u16>().unwrap());
        if expected_allowed {
            assert!(response.errors.is_empty());
        } else {
            assert_eq!(response.errors.len(), 1);
            assert_eq!(response.errors[0].code, cells[10]);
            assert_eq!(
                response.errors[0].extensions.get("actual_cost"),
                Some(&cost)
            );
            assert_eq!(
                response.errors[0].extensions.get("cost_limit"),
                Some(&cells[7].parse::<u32>().unwrap())
            );
        }
    }
}

#[test]
fn invalid_configuration_is_rejected() {
    let mut invalid = config(true);
    invalid.tier_limits.remove("standard");
    assert!(block_on(QueryBudget::new(invalid)).is_err());

    let mut invalid = config(true);
    invalid.client_tier_header.clear();
    assert!(block_on(QueryBudget::new(invalid)).is_err());

    let mut invalid = config(true);
    invalid.mutation_max_cost = 0;
    assert!(block_on(QueryBudget::new(invalid)).is_err());

    let mut invalid = config(true);
    invalid.rejection_status = 0;
    assert!(block_on(QueryBudget::new(invalid)).is_err());
}
