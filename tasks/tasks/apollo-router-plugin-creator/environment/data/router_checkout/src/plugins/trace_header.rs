use crate::framework::{router, Plugin};

#[derive(Clone, Debug)]
pub struct TraceHeaderConfig {
    pub enabled: bool,
    pub header_name: String,
}

#[derive(Clone, Debug)]
pub struct TraceHeader {
    configuration: TraceHeaderConfig,
}

impl Plugin for TraceHeader {
    type Config = TraceHeaderConfig;

    async fn new(configuration: Self::Config) -> Result<Self, String> {
        if configuration.header_name.trim().is_empty() {
            return Err("header_name must not be empty".to_string());
        }
        Ok(Self { configuration })
    }

    fn router_service(&self, service: router::BoxService) -> router::BoxService {
        if !self.configuration.enabled {
            return service;
        }
        let header_name = self.configuration.header_name.clone();
        Box::new(move |mut request| {
            if let Some(value) = request.headers.get(&header_name).map(str::to_owned) {
                request.context.insert("acme.trace_id", value);
            }
            service(request)
        })
    }
}

crate::register_plugin!("acme", "trace_header", TraceHeader);
