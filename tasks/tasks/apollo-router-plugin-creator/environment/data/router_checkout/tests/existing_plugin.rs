use acme_router_fixture::framework::{block_on, router, Plugin};
use acme_router_fixture::plugins::trace_header::{TraceHeader, TraceHeaderConfig, REGISTRATION};

#[test]
fn existing_trace_plugin_documents_the_local_convention() {
    let plugin = block_on(TraceHeader::new(TraceHeaderConfig {
        enabled: true,
        header_name: "x-trace-id".to_string(),
    }))
    .unwrap();
    let response = plugin
        .router_service(router::passthrough())(
        router::Request::default().with_header("X-Trace-ID", "trace-17"),
    );
    assert_eq!(response.context.get("acme.trace_id"), Some("trace-17"));
    assert_eq!(REGISTRATION.namespace, "acme");
    assert_eq!(REGISTRATION.name, "trace_header");
}
