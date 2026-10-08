#include "testing/gtest/include/gtest/gtest.h"

#include <string>

namespace bedrock {

std::string FormatForDisplay(const std::string& input) {
  return input.empty() ? "(empty)" : input;
}

TEST(UrlFormatterTest, FormatsEmptyLabel) {
  EXPECT_EQ("(empty)", FormatForDisplay(""));
}

TEST(UrlFormatterTest, PreservesBookmarkLabel) {
  EXPECT_EQ("Bookmarks", FormatForDisplay("Bookmarks"));
}

}  // namespace bedrock
