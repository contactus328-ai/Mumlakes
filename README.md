# Mumbai Lake Water Levels

Daily tracker for the seven lakes that supply Mumbai's drinking water (Bhatsa,
Upper Vaitarna, Middle Vaitarna, Modak Sagar, Tansa, Vihar, Tulsi).

A GitHub Actions workflow (`.github/workflows/daily-update.yml`) runs
`scripts/fetch_lake_levels.py` every morning. It scrapes the daily figures
from [mumbailakewaterlevel.in](https://mumbailakewaterlevel.in/) — which
itself sources them from the BMC Hydraulic Engineer's Department, Bhandup
Complex — appends them to `data/history.csv`, and writes `data/latest.json`.
`index.html`, served via GitHub Pages, reads those files and renders the
dashboard.

Run manually:

```
pip install -r requirements.txt
python scripts/fetch_lake_levels.py
```
