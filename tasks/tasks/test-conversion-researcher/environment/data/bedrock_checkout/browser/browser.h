#pragma once

namespace bedrock {

class WebContents;

class Browser {
 public:
  WebContents* active_web_contents() const { return active_web_contents_; }
  void SetActiveWebContentsForTesting(WebContents* contents) {
    active_web_contents_ = contents;
  }

 private:
  WebContents* active_web_contents_ = nullptr;
};

}  // namespace bedrock
