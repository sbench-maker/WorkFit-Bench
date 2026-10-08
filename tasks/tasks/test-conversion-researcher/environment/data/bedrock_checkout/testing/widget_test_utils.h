#pragma once

namespace bedrock {

class BaseWindow;

namespace test {

void WaitForWindowVisible(BaseWindow* window);
void WaitForWindowClosed(BaseWindow* window);

}  // namespace test
}  // namespace bedrock
