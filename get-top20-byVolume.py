import subprocess
import json
import os
import pandas as pd
from pathlib import Path

# 1) Get all pairs from freqtrade list pairs
#    This will produce a JSON list of pairs if you use "--format json".
def get_all_pairs():
    cmd = [
        "freqtrade", "list", "pairs",
        "--exchange", "binance",
        "--format", "json"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    result.check_returncode()  # Raises an error if freqtrade fails
    all_pairs = json.loads(result.stdout)
    return all_pairs

def download_data_for_pair(pair, timeframe="5m", start="20210101", end="20230101"):
    """
    Downloads OHLCV data for the specified pair, timeframe, and date range.
    Data stored inside freqtrade's user_data/data/<exchange> directory.
    """
    cmd = [
        "freqtrade", "download-data",
        "--exchange", "binance",
        "--pairs", pair,
        "--timeframe", timeframe,
        "--timerange", f"{start}-{end}",
        "--add-exchange-prefix"  # so each pair is in its own file/folder
    ]
    print(f"Downloading data for {pair}...")
    subprocess.run(cmd, check=True)

def load_and_sum_volume(pair, timeframe="5m", start="20210101", end="20230101"):
    """
    Loads the downloaded OHLCV data for `pair` and sums the volume column.
    Adjust if you're storing in a different format (e.g., JSON, CSV, etc.).
    """
    # Freqtrade typically stores JSON lines in a file path like:
    # user_data/data/binance/PAR_USDT-5m.json
    # But the EXACT path depends on your freqtrade version/flags.
    # We'll guess the naming pattern:
    data_dir = Path("user_data/data/binance")
    # Construct filename. If you used "--add-exchange-prefix" then it might look like:
    # 'binance_BTC-USDT_5m.json'
    # Adjust if needed.
    # Note: in dev builds, the naming might differ. You may need to debug your actual filenames.
    filename = f"binance_{pair.replace('/', '-')}_{timeframe}.json"
    filepath = data_dir / filename

    if not filepath.exists():
        print(f"No data file found for {pair} at {filepath}.")
        return 0.0

    # Parse freqtrade's JSON. It's JSON lines (one object per line).
    # We'll read line by line and parse into a dataframe.
    rows = []
    with open(filepath, "r") as f:
        for line in f:
            row = json.loads(line)
            # row = [timestamp, open, high, low, close, volume]
            # freqtrade’s internal format for each candle is typically a list.
            # If that's changed in dev builds, adjust accordingly.
            rows.append(row)

    # Convert to a dataframe
    df = pd.DataFrame(rows, columns=["date", "open", "high", "low", "close", "volume"])
    # Convert numeric columns
    numeric_cols = ["open", "high", "low", "close", "volume"]
    df[numeric_cols] = df[numeric_cols].apply(pd.to_numeric)
    # Sum volume
    total_volume = df["volume"].sum()
    return total_volume

def main():
    # Decide your date range
    start_date = "20210101"  # Jan 1, 2021
    end_date   = "20230101"  # Jan 1, 2023
    timeframe  = "5m"

    # 1) Get all binance pairs in JSON format
    all_pairs_info = get_all_pairs()

    # 2) Filter to only /USDT pairs
    usdt_pairs = [p["pair"] for p in all_pairs_info if p["pair"].endswith("/USDT")]

    # 3) OPTIONAL: Limit to 50 or 100 pairs to avoid huge data downloads (just an example)
    usdt_pairs = usdt_pairs[:100]

    # 4) Download data for each pair
    for pair in usdt_pairs:
        download_data_for_pair(pair, timeframe, start_date, end_date)

    # 5) Sum the volume for each pair
    pair_volumes = []
    for pair in usdt_pairs:
        vol = load_and_sum_volume(pair, timeframe, start_date, end_date)
        pair_volumes.append((pair, vol))
        print(f"Pair {pair} => total volume: {vol}")

    # 6) Sort by total volume descending
    pair_volumes.sort(key=lambda x: x[1], reverse=True)

    # 7) Pick top 20
    top_20 = pair_volumes[:20]
    print("Top 20 pairs by total volume over the last 2 years:")
    for p, v in top_20:
        print(f"{p}: {v}")

    # 8) Create a new config with these pairs in StaticPairList
    #    We’ll just print JSON snippet to console.
    #    You could also write to a file.
    config_snippet = {
        "pairlists": [
            {
                "method": "StaticPairList",
                "pairs": [ p[0] for p in top_20 ]
            }
        ]
    }
    print("You can merge this snippet into your config.json:\n")
    print(json.dumps(config_snippet, indent=4))


if __name__ == "__main__":
    main()
