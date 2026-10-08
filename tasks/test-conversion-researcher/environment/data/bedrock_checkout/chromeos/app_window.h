#pragma once

#include <memory>

namespace bedrock {

class BaseWindow;

class AppWindow {
 public:
  AppWindow();
  ~AppWindow();

  void Init();
  void Show();
  bool initialized() const { return initialized_; }
  BaseWindow* GetBaseWindow() const { return base_window_.get(); }

 private:
  bool initialized_ = false;
  std::unique_ptr<BaseWindow> base_window_;
};

}  // namespace bedrock
