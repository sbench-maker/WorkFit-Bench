#include "chromeos/app_window.h"
#include "chromeos/base_window.h"
#include "testing/browser_test.h"
#include "testing/widget_test_utils.h"

namespace bedrock {

class ExistingAppWindowBrowserTest : public InProcessBrowserTest {
 protected:
  void TearDownOnMainThread() override {
    if (window_ && window_->GetBaseWindow()) {
      BaseWindow* native_window = window_->GetBaseWindow();
      native_window->Close();
      test::WaitForWindowClosed(native_window);
    }
    window_.reset();
    InProcessBrowserTest::TearDownOnMainThread();
  }

  std::unique_ptr<AppWindow> window_;
};

IN_PROC_BROWSER_TEST_F(ExistingAppWindowBrowserTest, ShowsInitializedWindow) {
  window_ = std::make_unique<AppWindow>();
  window_->Init();
  window_->Show();
  test::WaitForWindowVisible(window_->GetBaseWindow());
  EXPECT_TRUE(window_->GetBaseWindow()->IsVisible());
}

}  // namespace bedrock
