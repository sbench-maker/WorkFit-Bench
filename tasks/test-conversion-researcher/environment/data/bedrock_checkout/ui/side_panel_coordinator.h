#pragma once

#include <memory>

namespace bedrock {

class AppWindow;

class SidePanelCoordinator {
 public:
  SidePanelCoordinator();
  ~SidePanelCoordinator();

  AppWindow* CreateDetachedWindow();
  void CloseDetachedWindow();
  AppWindow* detached_window_for_testing() const { return detached_window_.get(); }

 private:
  std::unique_ptr<AppWindow> detached_window_;
};

}  // namespace bedrock
