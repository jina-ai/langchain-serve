#!/usr/bin/env bash

set -ex

TEST_SUITE=$1
DEFAULT_BATCH_SIZE=5
BATCH_SIZE="${2:-$DEFAULT_BATCH_SIZE}"

declare -a unit_tests=($(find tests/unit -name "test_*.py"))
declare -a integration_tests_local=($(find tests/integration/local -name "test_*.py"))
declare -a integration_tests_jcloud=($(find tests/integration/jcloud -name "test_*.py"))
declare -a all_tests=("${unit_tests[@]}" "${integration_tests[@]}")

if [ "$TEST_SUITE" == "unit" ]; then
    dest="$(echo "${unit_tests[@]}" | xargs -n$BATCH_SIZE)"
elif [[ "$TEST_SUITE" == "integration_local" ]]; then
    dest="$(echo "${integration_tests_local[@]}" | xargs -n$BATCH_SIZE)"
elif [[ "$TEST_SUITE" == "integration_jcloud" ]]; then
    dest="$(echo "${integration_tests_jcloud[@]}" | xargs -n$BATCH_SIZE)"
else
    dest="$(echo "${all_tests[@]}" | xargs -n$BATCH_SIZE)"
fi

printf '%s\n' "${dest[@]}" | jq -R . | jq -cs .
