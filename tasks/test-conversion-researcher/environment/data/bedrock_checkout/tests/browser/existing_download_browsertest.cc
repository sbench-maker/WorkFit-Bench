#include "browser/browser.h"
#include "browser/web_contents.h"
#include "testing/browser_test.h"

namespace bedrock {

class ExistingDownloadBrowserTest : public InProcessBrowserTest {
 protected:
  void SetUpOnMainThread() override {
    InProcessBrowserTest::SetUpOnMainThread();
    const std::string url = GetTestUrl("/ready.html");
    TestNavigationObserver observer(url);
    observer.StartWatchingNewWebContents();
    browser()->active_web_contents()->Navigate(url);
    observer.Wait();
  }
};

IN_PROC_BROWSER_TEST_F(ExistingDownloadBrowserTest, HasCommittedPage) {
  EXPECT_TRUE(
      browser()->active_web_contents()->HasCommittedPrimaryMainFrame());
  EXPECT_GT(
      browser()->active_web_contents()->GetPrimaryMainFrameProcessId(), 0);
}

}  // namespace bedrock
