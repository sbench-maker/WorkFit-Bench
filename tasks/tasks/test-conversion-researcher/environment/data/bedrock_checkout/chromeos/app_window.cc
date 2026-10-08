#include "chromeos/app_window.h"

#include "chromeos/base_window.h"
#include "chromeos/multi_user_window_manager.h"

namespace bedrock {

namespace {
class NativeAppWindow : public BaseWindow {
 public:
  void Close() override { visible_ = false; }
  bool IsVisible() const override { return visible_; }
  void Show() { visible_ = true; }

 private:
  bool visible_ = false;
};
}  // namespace

AppWindow::AppWindow() = default;
AppWindow::~AppWindow() = default;

void AppWindow::Init() {
  base_window_ = std::make_unique<NativeAppWindow>();
  initialized_ = true;
  MultiUserWindowManager::Get()->RegisterWindow(this);
}

void AppWindow::Show() {
  if (!initialized_)
    return;
  static_cast<NativeAppWindow*>(base_window_.get())->Show();
}

}  // namespace bedrock
