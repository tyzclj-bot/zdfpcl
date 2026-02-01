
import sys

try:
    from supabase import create_client
    with open("status.txt", "w") as f:
        f.write("Success")
except Exception as e:
    with open("status.txt", "w") as f:
        f.write(f"Failed: {e}")
