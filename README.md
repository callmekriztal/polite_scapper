# The Polite Scraper — FlyRank Internship Backend Track W5 A9

Please see the full documentation in [`scraper/README.md`](scraper/README.md).

### Quickstart

```bash
# Create virtual environment & install requirements
python3 -m venv venv
source venv/bin/activate
pip install -r scraper/requirements.txt

# Scrape a website (pass the URL on the command line)
python scraper/src/main.py https://books.toscrape.com

# Scrape any other website (generic mode)
python scraper/src/main.py https://quotes.toscrape.com --mode generic --pages 5

# Run tests
pytest scraper/tests/ -v
```
