#include "ui/side_panel_coordinator.h"

#include "chromeos/app_window.h"
#include "chromeos/base_window.h"

namespace bedrock {

SidePanelCoordinator::SidePanelCoordinator() = default;
SidePanelCoordinator::~SidePanelCoordinator() = default;

AppWindow* SidePanelCoordinator::CreateDetachedWindow() {
  detached_window_ = std::make_unique<AppWindow>();
  detached_window_->Init();
  detached_window_->Show();
  return detached_window_.get();
}

void SidePanelCoordinator::CloseDetachedWindow() {
  // Closing the native surface delivers observer notifications before the
  // owning coordinator releases its AppWindow.
  if (detached_window_ && detached_window_->GetBaseWindow())
    detached_window_->GetBaseWindow()->Close();
}

}  // namespace bedrock
