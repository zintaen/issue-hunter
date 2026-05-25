#!/bin/bash
set -e

PROVIDER=$1
MODEL=$2
API_KEY=$3
GITHUB_TOKEN=$4
REPOSITORY=$5
ISSUE_NUMBER=$6

echo "Starting Issue Hunter GitHub Action..."
echo "Target Repository: $REPOSITORY"
echo "Issue Number: $ISSUE_NUMBER"
echo "Provider: $PROVIDER"

python main.py \
    --repo "$REPOSITORY" \
    --issues "$ISSUE_NUMBER" \
    --github-token "$GITHUB_TOKEN" \
    --api-key "$API_KEY" \
    --model "$MODEL" \
    --provider "$PROVIDER" \
    --dry-run
