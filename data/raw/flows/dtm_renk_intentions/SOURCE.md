# IOM DTM South Sudan - Renk Transit Center Intention Survey (7-11 Jul 2024)

- Page: https://dtm.iom.int/datasets/south-sudan-intention-survey-renk-transit-center-july-2024
- File: https://dtm.iom.int/dtm_download_track/61561?file=1&type=node&id=41946, saved manually because dtm.iom.int blocks scripted downloads.
- Converter: `scripts/fetch_flows_dtm_renk_intentions.py`, which writes `data/processed/flows/dtm_renk_intentions_flows.csv`.
- Coverage: 652 sampled households, out of 10,735 people present.
- Conversion: Renk (SS0711) to each household's intended county in South Sudan. Counts are surveyed household members and are not scaled up; quality = `intention_survey_sample`. 1,273 people are kept. 1,647 are dropped because they stay in Renk, are going abroad, or gave no answer.
- The Dec 2023 and Mar 2024 Renk intention reports, which are PDFs, give destinations by state only, so they are not used.
