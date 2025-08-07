#!/bin/bash
#
# Run all test files in the mimi2 project
# This script runs each test file and tracks pass/fail status
#

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Test files to run (in order of dependency/importance)
TEST_FILES=(
    "test_imports.py"
    "test_message_splitter.py"
    "test_database.py"
    "test_integration.py"
    "test_config.py"
    "test_api.py"
    "test_requirements_verification.py"
    "test_final_verification.py"
)

# Track results
PASSED=0
FAILED=0
FAILED_TESTS=()

echo -e "${BLUE}🧪 Running Mimi2 Test Suite${NC}"
echo -e "${BLUE}============================${NC}"
echo ""

# Function to run a single test
run_test() {
    local test_file=$1
    local test_name=$(basename "$test_file" .py)
    
    echo -e "${YELLOW}📋 Running $test_name...${NC}"
    
    if uv run python "$test_file"; then
        echo -e "${GREEN}✅ $test_name PASSED${NC}"
        ((PASSED++))
    else
        echo -e "${RED}❌ $test_name FAILED${NC}"
        ((FAILED++))
        FAILED_TESTS+=("$test_name")
    fi
    echo ""
}

# Run each test file
for test_file in "${TEST_FILES[@]}"; do
    if [[ -f "$test_file" ]]; then
        run_test "$test_file"
    else
        echo -e "${RED}⚠️  Test file $test_file not found, skipping...${NC}"
        echo ""
    fi
done

# Summary
echo -e "${BLUE}=============================${NC}"
echo -e "${BLUE}📊 Test Suite Summary${NC}"
echo -e "${BLUE}=============================${NC}"
echo -e "Total tests run: $((PASSED + FAILED))"
echo -e "${GREEN}✅ Passed: $PASSED${NC}"
echo -e "${RED}❌ Failed: $FAILED${NC}"

if [[ $FAILED -gt 0 ]]; then
    echo ""
    echo -e "${RED}Failed tests:${NC}"
    for failed_test in "${FAILED_TESTS[@]}"; do
        echo -e "${RED}  - $failed_test${NC}"
    done
    echo ""
    echo -e "${RED}🚨 Some tests failed! Please check the output above.${NC}"
    exit 1
else
    echo ""
    echo -e "${GREEN}🎉 All tests passed! 🎉${NC}"
    exit 0
fi
