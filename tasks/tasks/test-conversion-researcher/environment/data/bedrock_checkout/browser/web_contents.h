#pragma once

#include <string>

namespace bedrock {

class WebContents {
 public:
  static WebContents* Create();

  void Navigate(const std::string& url);
  bool HasCommittedPrimaryMainFrame() const;
  int GetPrimaryMainFrameProcessId() const;

  // Unit-only escape hatch used by the old partial fixture.
  void SetProcessForTesting(int process_id);

 private:
  bool committed_ = false;
  int process_id_ = -1;
};

}  // namespace bedrock
