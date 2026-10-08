#include "chromeos/app_window.h"
#include "chromeos/base_window.h"
#include "chromeos/multi_user_window_manager.h"
#include "testing/gtest/include/gtest/gtest.h"
#include "ui/side_panel_coordinator.h"

namespace bedrock {

TEST(SidePanelCoordinatorTest, DetachedWindowIsInitializedAndRegistered) {
  SidePanelCoordinator coordinator;
  AppWindow* window = coordinator.CreateDetachedWindow();
  EXPECT_TRUE(window->initialized());
  EXPECT_TRUE(MultiUserWindowManager::Get()->IsRegistered(window));
  EXPECT_TRUE(window->GetBaseWindow()->IsVisible());
}

TEST(SidePanelCoordinatorTest, CloseDetachedWindowHidesNativeWindow) {
  SidePanelCoordinator coordinator;
  AppWindow* window = coordinator.CreateDetachedWindow();
  coordinator.CloseDetachedWindow();
  EXPECT_FALSE(window->GetBaseWindow()->IsVisible());
}

}  // namespace bedrock
