use std::collections::BTreeMap;
use std::future::Future;
use std::sync::Arc;
use std::task::{Context as TaskContext, Poll, Wake, Waker};

#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct Context {
    values: BTreeMap<String, String>,
}

impl Context {
    pub fn insert(&mut self, key: impl Into<String>, value: impl Into<String>) {
        self.values.insert(key.into(), value.into());
    }

    pub fn get(&self, key: &str) -> Option<&str> {
        self.values.get(key).map(String::as_str)
    }
}

#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct Headers(BTreeMap<String, String>);

impl Headers {
    pub fn insert(&mut self, name: impl Into<String>, value: impl Into<String>) {
        self.0.insert(name.into().to_ascii_lowercase(), value.into());
    }

    pub fn get(&self, name: &str) -> Option<&str> {
        self.0
            .get(&name.to_ascii_lowercase())
            .map(String::as_str)
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum OperationKind {
    Query,
    Mutation,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct QueryPlan {
    pub estimated_cost: u32,
    pub operation_kind: OperationKind,
}

impl QueryPlan {
    pub fn contains_mutations(&self) -> bool {
        self.operation_kind == OperationKind::Mutation
    }
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct GraphQLError {
    pub message: String,
    pub code: String,
    pub extensions: BTreeMap<String, u32>,
}

impl GraphQLError {
    pub fn budget(message: String, code: String, actual_cost: u32, cost_limit: u32) -> Self {
        Self {
            message,
            code,
            extensions: BTreeMap::from([
                ("actual_cost".to_string(), actual_cost),
                ("cost_limit".to_string(), cost_limit),
            ]),
        }
    }
}

pub mod router {
    use super::{Context, Headers};

    #[derive(Clone, Debug, Default, PartialEq, Eq)]
    pub struct Request {
        pub headers: Headers,
        pub context: Context,
    }

    impl Request {
        pub fn with_header(mut self, name: &str, value: &str) -> Self {
            self.headers.insert(name, value);
            self
        }
    }

    #[derive(Clone, Debug, PartialEq, Eq)]
    pub struct Response {
        pub status_code: u16,
        pub context: Context,
    }

    pub type BoxService = Box<dyn Fn(Request) -> Response + Send + Sync + 'static>;

    pub fn passthrough() -> BoxService {
        Box::new(|request| Response {
            status_code: 204,
            context: request.context,
        })
    }
}

pub mod execution {
    use super::{Context, GraphQLError, QueryPlan};

    #[derive(Clone, Debug, PartialEq, Eq)]
    pub struct Request {
        pub query_plan: QueryPlan,
        pub context: Context,
    }

    #[derive(Clone, Debug, PartialEq, Eq)]
    pub struct Response {
        pub status_code: u16,
        pub context: Context,
        pub errors: Vec<GraphQLError>,
        pub executed: bool,
    }

    impl Response {
        pub fn rejected(status_code: u16, context: Context, error: GraphQLError) -> Self {
            Self {
                status_code,
                context,
                errors: vec![error],
                executed: false,
            }
        }
    }

    pub type BoxService = Box<dyn Fn(Request) -> Response + Send + Sync + 'static>;

    pub fn passthrough() -> BoxService {
        Box::new(|request| Response {
            status_code: 200,
            context: request.context,
            errors: Vec::new(),
            executed: true,
        })
    }
}

pub trait Plugin: Sized {
    type Config;

    async fn new(config: Self::Config) -> Result<Self, String>;

    fn router_service(&self, service: router::BoxService) -> router::BoxService {
        service
    }

    fn execution_service(&self, service: execution::BoxService) -> execution::BoxService {
        service
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct PluginRegistration {
    pub namespace: &'static str,
    pub name: &'static str,
    pub plugin_type: &'static str,
}

#[macro_export]
macro_rules! register_plugin {
    ($namespace:literal, $name:literal, $plugin:ty) => {
        pub const REGISTRATION: $crate::framework::PluginRegistration =
            $crate::framework::PluginRegistration {
                namespace: $namespace,
                name: $name,
                plugin_type: stringify!($plugin),
            };
    };
}

struct NoopWake;

impl Wake for NoopWake {
    fn wake(self: Arc<Self>) {}
}

pub fn block_on<F: Future>(future: F) -> F::Output {
    let waker = Waker::from(Arc::new(NoopWake));
    let mut task_context = TaskContext::from_waker(&waker);
    let mut future = Box::pin(future);
    loop {
        match future.as_mut().poll(&mut task_context) {
            Poll::Ready(value) => return value,
            Poll::Pending => std::thread::yield_now(),
        }
    }
}
