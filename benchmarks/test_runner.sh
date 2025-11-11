#!/bin/bash
# Quick test script to verify the benchmark runner works

echo "=== Co-Sight Benchmark Test ==="
echo ""

# Check if .env exists
if [ ! -f "../.env" ]; then
    echo "❌ Error: .env file not found in Co-Sight root directory"
    echo "Please create .env with your API keys"
    exit 1
fi

# Convert a small sample
echo "📝 Converting first English prompt to CSV..."
python convert_deepresearch_to_csv.py --language en --start 0 --end 1 --output data/test_prompt.csv

echo ""
echo "📋 Input prompt:"
cat data/test_prompt.csv
echo ""

# Run benchmark on 1 task
echo "🚀 Running benchmark on 1 task..."
python runner.py \
  --input data/test_prompt.csv \
  --output results/test_result.jsonl

echo ""
if [ -f "results/test_result.jsonl" ]; then
    echo "✅ Test completed successfully!"
    echo ""
    echo "📊 Result:"
    cat results/test_result.jsonl | python -m json.tool
    echo ""
    echo "Result saved to: results/test_result.jsonl"
else
    echo "❌ Test failed - no output file generated"
    exit 1
fi
