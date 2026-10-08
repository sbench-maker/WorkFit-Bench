#pragma once

namespace bedrock {

class BaseWindow {
 public:
  virtual ~BaseWindow() = default;
  virtual void Close() = 0;
  virtual bool IsVisible() const = 0;
};

}  // namespace bedrock
