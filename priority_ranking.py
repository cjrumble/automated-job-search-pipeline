import pandas as pd


# FIX 6: The original file was two bare lines referencing an undefined `df`.
# Importing it caused NameError. Rewritten as proper callable functions.

def rank_jobs(jobs):
    """
    Sorts a list of job dicts by Fit Score (highest first) and assigns
    sequential Priority numbers starting at 1.

    Args:
        jobs: list of dicts, each expected to have a "Fit Score" key
    Returns:
        list of dicts with "Priority" key added, sorted by Fit Score desc
    """
    if not jobs:
        return []

    df = pd.DataFrame(jobs)

    if "Fit Score" not in df.columns:
        print("[rank_jobs] Warning: 'Fit Score' column not found — returning unsorted.")
        return jobs

    df = (
        df.sort_values(by="Fit Score", ascending=False)
          .reset_index(drop=True)
    )
    df["Priority"] = range(1, len(df) + 1)

    return df.to_dict("records")


def get_top_jobs(jobs, n=10):
    """
    Returns the top N jobs from an already-ranked list.

    Expects jobs to have already been passed through rank_jobs().
    Does not re-sort — slices the first n entries by Priority.

    Args:
        jobs: list of ranked job dicts (output of rank_jobs())
        n:    how many top jobs to return (default 10)
    Returns:
        list of up to n job dicts
    """
    return jobs[:n]
