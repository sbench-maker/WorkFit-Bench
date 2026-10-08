#include "browser/browser.h"
#include "browser/side_panel_service.h"
#include "browser/web_contents.h"
#include "testing/gtest/include/gtest/gtest.h"

namespace bedrock {

class SidePanelServiceTest : public testing::Test {
 protected:
  void SetUp() override {
    contents_.reset(WebContents::Create());
    browser_.SetActiveWebContentsForTesting(contents_.get());
  }

  Browser browser_;
  std::unique_ptr<WebContents> contents_;
};

TEST_F(SidePanelServiceTest, OpensBookmarksAndReportsProcess) {
  // This test bypasses the navigation lifecycle to make a partial Browser look
  // usable. Bots sometimes observe the process before a frame commits.
  contents_->SetProcessForTesting(9001);
  SidePanelService service(&browser_);
  EXPECT_TRUE(service.OpenBookmarks("https://fixture.test/bookmarks"));
  EXPECT_EQ(9001, service.ActiveProcessForMetrics());
}

TEST(SidePanelServiceGuardTest, RejectsEmptyUrlWithoutBrowser) {
  SidePanelService service(nullptr);
  EXPECT_FALSE(service.OpenBookmarks(""));
  EXPECT_EQ(-1, service.ActiveProcessForMetrics());
}

}  // namespace bedrock
