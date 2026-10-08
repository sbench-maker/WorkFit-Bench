#pragma once

#include <set>

namespace bedrock {

class AppWindow;

class MultiUserWindowManager {
 public:
  static MultiUserWindowManager* Get();
  void RegisterWindow(AppWindow* window);
  bool IsRegistered(AppWindow* window) const;

 private:
  std::set<AppWindow*> windows_;
};

}  // namespace bedrock
