#pragma once

#include <string>

namespace bedrock {

class Browser;

class SidePanelService {
 public:
  explicit SidePanelService(Browser* browser);

  bool OpenBookmarks(const std::string& url);
  int ActiveProcessForMetrics() const;

 private:
  Browser* browser_;
};

}  // namespace bedrock
