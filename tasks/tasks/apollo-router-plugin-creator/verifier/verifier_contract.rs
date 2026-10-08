use std::collections::BTreeMap;
use std::sync::atomic::{AtomicUsize, Ordering};
use std::sync::Arc;

use acme_router_fixture::framework::{
    block_on, execution, router, Context, OperationKind, Plugin, QueryPlan,
};
use acme_router_fixture::plugins::query_budget::{
    QueryBudget, QueryBudgetConfig, TIER_CONTEXT_KEY, REGISTRATION,
};

fn alternate_config(enabled: bool) -> QueryBudgetConfig {
    QueryBudgetConfig {
        enabled,
        client_tier_header: "x-budget-class".to_string(),
        default_tier: "bronze".to_string(),
        tier_limits: BTreeMap::from([
            ("bronze".to_string(), 13),
            ("gold".to_string(), 29),
        ]),
        mutation_max_cost: 11,
        rejection_status: 202,
        error_code: "BUDGET_BLOCKED".to_string(),
        error_message: "Alternate fixture budget exceeded".to_string(),
    }
}

fn execution_request(cost: u32, operation_kind: OperationKind, context: Context) -> execution::Request {
    execution::Request {
        query_plan: QueryPlan {
            estimated_cost: cost,
            operation_kind,
        },
        context,
    }
}

#[test]
fn verifier_router_capture() {
    let plugin = block_on(QueryBudget::new(alternate_config(true))).unwrap();
    let response = plugin.router_service(router::passthrough())(
        router::Request::default().with_header("X-Budget-Class", "  GoLd "),
    );
    assert_eq!(response.context.get(TIER_CONTEXT_KEY), Some("gold"));

    let unknown = plugin.router_service(router::passthrough())(
        router::Request::default().with_header("x-budget-class", "platinum"),
    );
    assert_eq!(unknown.context.get(TIER_CONTEXT_KEY), Some("bronze"));

    let missing = plugin.router_service(router::passthrough())(router::Request::default());
    assert_eq!(missing.context.get(TIER_CONTEXT_KEY), Some("bronze"));
}

#[test]
fn verifier_execution_limits_and_errors() {
    let plugin = block_on(QueryBudget::new(alternate_config(true))).unwrap();
    let mut gold = Context::default();
    gold.insert(TIER_CONTEXT_KEY, "gold");

    let at_query_limit = plugin.execution_service(execution::passthrough())(execution_request(
        29,
        OperationKind::Query,
        gold.clone(),
    ));
    assert!(at_query_limit.executed);
    assert!(at_query_limit.errors.is_empty());

    let over_query_limit = plugin.execution_service(execution::passthrough())(execution_request(
        30,
        OperationKind::Query,
        gold.clone(),
    ));
    assert!(!over_query_limit.executed);
    assert_eq!(over_query_limit.status_code, 202);
    assert_eq!(over_query_limit.errors.len(), 1);
    let error = &over_query_limit.errors[0];
    assert_eq!(error.code, "BUDGET_BLOCKED");
    assert_eq!(error.message, "Alternate fixture budget exceeded");
    assert_eq!(error.extensions.get("actual_cost"), Some(&30));
    assert_eq!(error.extensions.get("cost_limit"), Some(&29));

    let at_mutation_limit = plugin.execution_service(execution::passthrough())(execution_request(
        11,
        OperationKind::Mutation,
        gold.clone(),
    ));
    assert!(at_mutation_limit.executed);

    let over_mutation_limit = plugin.execution_service(execution::passthrough())(execution_request(
        12,
        OperationKind::Mutation,
        gold,
    ));
    assert!(!over_mutation_limit.executed);
    assert_eq!(over_mutation_limit.errors[0].extensions.get("cost_limit"), Some(&11));
}

#[test]
fn verifier_passthrough_and_short_circuit() {
    let disabled = block_on(QueryBudget::new(alternate_config(false))).unwrap();
    let router_calls = Arc::new(AtomicUsize::new(0));
    let router_counter = Arc::clone(&router_calls);
    let router_inner: router::BoxService = Box::new(move |request| {
        router_counter.fetch_add(1, Ordering::SeqCst);
        router::Response {
            status_code: 207,
            context: request.context,
        }
    });
    let routed = disabled.router_service(router_inner)(
        router::Request::default().with_header("x-budget-class", "gold"),
    );
    assert_eq!(routed.status_code, 207);
    assert_eq!(routed.context.get(TIER_CONTEXT_KEY), None);
    assert_eq!(router_calls.load(Ordering::SeqCst), 1);

    let execution_calls = Arc::new(AtomicUsize::new(0));
    let execution_counter = Arc::clone(&execution_calls);
    let execution_inner: execution::BoxService = Box::new(move |request| {
        execution_counter.fetch_add(1, Ordering::SeqCst);
        execution::Response {
            status_code: 206,
            context: request.context,
            errors: Vec::new(),
            executed: true,
        }
    });
    let disabled_response = disabled.execution_service(execution_inner)(execution_request(
        999,
        OperationKind::Mutation,
        Context::default(),
    ));
    assert_eq!(disabled_response.status_code, 206);
    assert_eq!(execution_calls.load(Ordering::SeqCst), 1);

    let enabled = block_on(QueryBudget::new(alternate_config(true))).unwrap();
    let blocked_calls = Arc::new(AtomicUsize::new(0));
    let blocked_counter = Arc::clone(&blocked_calls);
    let blocked_inner: execution::BoxService = Box::new(move |request| {
        blocked_counter.fetch_add(1, Ordering::SeqCst);
        execution::passthrough()(request)
    });
    let blocked = enabled.execution_service(blocked_inner)(execution_request(
        14,
        OperationKind::Query,
        Context::default(),
    ));
    assert!(!blocked.executed);
    assert_eq!(blocked_calls.load(Ordering::SeqCst), 0);

    let allowed_calls = Arc::new(AtomicUsize::new(0));
    let allowed_counter = Arc::clone(&allowed_calls);
    let allowed_inner: execution::BoxService = Box::new(move |request| {
        allowed_counter.fetch_add(1, Ordering::SeqCst);
        execution::passthrough()(request)
    });
    let allowed = enabled.execution_service(allowed_inner)(execution_request(
        13,
        OperationKind::Query,
        Context::default(),
    ));
    assert!(allowed.executed);
    assert_eq!(allowed_calls.load(Ordering::SeqCst), 1);
}

#[test]
fn verifier_registration() {
    assert_eq!(REGISTRATION.namespace, "acme");
    assert_eq!(REGISTRATION.name, "query_budget");
    assert!(REGISTRATION.plugin_type.ends_with("QueryBudget"));
}
