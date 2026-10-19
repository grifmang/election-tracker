import subprocess, sys, os
here = os.path.dirname(os.path.abspath(__file__))
for s in ["fetch_races.py", "fetch_early_vote.py", "fetch_results.py"]:
    print("==", s); subprocess.run([sys.executable, os.path.join(here, s)], check=True, cwd=here)
subprocess.run([sys.executable, os.path.join(here, "fetch_results.py"), "--test2024"], check=True, cwd=here)
