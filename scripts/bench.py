"""Quick latency benchmark — bypasses CLI to measure pipeline stages."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.synthesis.chain import query

q = sys.argv[1] if len(sys.argv) > 1 else "How does the CCSDS packetizer create telemetry packets?"
result = query(q)
print(f"\nAnswer: {result.answer[:120]}...")
print(f"Sources: {len(result.sources)}")
print(f"Total latency: {result.latency_ms:.0f}ms")
