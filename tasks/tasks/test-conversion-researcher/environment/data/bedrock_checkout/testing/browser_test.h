#pragma once

#include <string>

namespace bedrock {

class Browser;

class InProcessBrowserTest {
 protected:
  virtual void SetUpOnMainThread() {}
  virtual void TearDownOnMainThread() {}
  Browser* browser() const;
  std::string GetTestUrl(const std::string& path) const;
};

class TestNavigationObserver {
 public:
  explicit TestNavigationObserver(const std::string& url);
  void StartWatchingNewWebContents();
  void Wait();
};

}  // namespace bedrock

#define IN_PROC_BROWSER_TEST_F(Fixture, Name) void Fixture##_##Name()
