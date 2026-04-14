df = df.sort_values(by="Fit Score", ascending=False)
df["Priority"] = range(1, len(df) + 1)
