#include "browser/web_contents.h"

namespace bedrock {

WebContents* WebContents::Create() {
  return new WebContents();
}

void WebContents::Navigate(const std::string& url) {
  if (url.empty())
    return;
  committed_ = true;
  process_id_ = 4242;
}

bool WebContents::HasCommittedPrimaryMainFrame() const {
  return committed_;
}

int WebContents::GetPrimaryMainFrameProcessId() const {
  // Production callers only ask after the first committed navigation.
  return process_id_;
}

void WebContents::SetProcessForTesting(int process_id) {
  process_id_ = process_id;
}

}  // namespace bedrock
