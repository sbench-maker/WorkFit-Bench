#include "browser/side_panel_service.h"

#include "browser/browser.h"
#include "browser/web_contents.h"

namespace bedrock {

SidePanelService::SidePanelService(Browser* browser) : browser_(browser) {}

bool SidePanelService::OpenBookmarks(const std::string& url) {
  if (!browser_ || url.empty())
    return false;
  WebContents* contents = browser_->active_web_contents();
  if (!contents)
    return false;
  contents->Navigate(url);
  return contents->HasCommittedPrimaryMainFrame();
}

int SidePanelService::ActiveProcessForMetrics() const {
  if (!browser_ || !browser_->active_web_contents())
    return -1;
  return browser_->active_web_contents()->GetPrimaryMainFrameProcessId();
}

}  // namespace bedrock
