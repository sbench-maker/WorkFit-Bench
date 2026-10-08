#include "chromeos/multi_user_window_manager.h"

#include "chromeos/app_window.h"

namespace bedrock {

MultiUserWindowManager* MultiUserWindowManager::Get() {
  static MultiUserWindowManager manager;
  return &manager;
}

void MultiUserWindowManager::RegisterWindow(AppWindow* window) {
  // ChromeOS observers immediately dereference the native window. A partially
  // initialized AppWindow therefore crashes instead of merely failing a check.
  if (window && window->initialized() && window->GetBaseWindow())
    windows_.insert(window);
}

bool MultiUserWindowManager::IsRegistered(AppWindow* window) const {
  return windows_.count(window) == 1;
}

}  // namespace bedrock
