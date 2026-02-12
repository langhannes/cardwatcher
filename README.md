# CardWatcher

A Flask web application for tracking CardMarket trading card listings over time. Monitor price changes, new listings, sold items, and relisting activity for your favorite cards.

![Search View](image-files/main-page.jpeg)

## Features

- **Price Tracking**: Track average prices and price changes over time (1 week, 1 month, 2 months, 6 months)
- **Sold Price Tracking**: Monitor ended/sold listing prices separately from available listings
- **Lowest Price Display**: See the minimum price for each card at a glance
- **Listing History**: See when listings were added, sold, or relisted
- **Search & Sort**: Search by card name, sort by price, price change, percentage change, or lowest price
- **Visual Indicators**: Color-coded badges showing availability changes (+added/-removed)
- **Single-Page Download**: Download button on each card's detail page for quick updates
- **Archive Support**: Archive cards you no longer want to actively track
- **Historical Data**: Maintains complete listing history including price changes per seller

## Prerequisites

- Python 3.8+
- Google Chrome browser (for Selenium downloader)

## Installation

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd cardmarket
   ```

2. **Create a virtual environment (recommended):**
   ```bash
   python -m venv venv

   # Windows
   venv\Scripts\activate

   # Linux/Mac
   source venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up the data repository:**
   ```bash
   # Clone or create the data repo as a sibling directory
   cd ..
   git clone <data-repository-url> cardwatcher-data
   # Or create a new one:
   mkdir cardwatcher-data
   cd cardwatcher-data
   mkdir pages archive images changes
   git init
   ```

   The directory structure should look like:
   ```
   parent/
   ├── cardwatcher/         (this repo)
   └── cardwatcher-data/    (data repo)
   ```

   The app will create missing directories on startup automatically.

## Project Structure

```
parent/
├── cardwatcher/                  # Application repo
│   ├── app/                      # Core application modules
│   │   ├── config.py             # Data directory configuration
│   │   ├── download_manager.py   # Background download manager for web UI
│   │   ├── language_libraries.py # Language/country mappings and flag sprites
│   │   ├── listing.py            # Listing class - represents a single seller listing
│   │   ├── page.py               # Page class - represents a tracked card with all listings
│   │   ├── selenium_downloader.py # Automated downloader using Selenium
│   │   ├── watcherbase.py        # Core utilities for importing and processing pages
│   │   ├── watchersearch.py      # Search view HTML generation
│   │   └── recalculate_metrics.py # Utility to recalculate all price metrics
│   ├── downloads/                # Temporary folder for downloaded HTML files
│   ├── static/                   # CSS, sprites, JS assets
│   ├── templates/                # Jinja2 HTML templates
│   │   ├── blanko.htm            # Individual card page template
│   │   └── search.htm            # Search/gallery view template
│   ├── cardwatcher.py            # Flask application entry point
│   ├── requirements.txt          # Python dependencies
│   └── README.md                 # This file
│
└── cardwatcher-data/             # Data repo (separate git repository)
    ├── pages/                    # Active card tracking data (JSON files)
    ├── archive/                  # Archived cards no longer actively tracked
    ├── images/                   # Card product images
    └── changes/                  # Tracking data
        └── price_history.json   # Unified price history with all metrics
```

## Usage

### Starting the Web Application

```bash
python cardwatcher.py
```

The application runs at `http://localhost:5000` by default.

**Command line options:**
```bash
python cardwatcher.py -p 5001    # Run on port 5001
python cardwatcher.py --port 8080  # Run on port 8080
```

Use a different port if you get "Address already in use" errors.

### Adding Cards to Track

CardMarket uses Cloudflare protection, so pages must be downloaded using the Selenium downloader or manually.

#### Adding a New Card (First Time Setup)

To start tracking a new card, you need to manually download it once:

1. **Find the card on CardMarket** - Navigate to the card's listing page (e.g., `https://www.cardmarket.com/en/Pokemon/Products/Singles/Base-Set/Charizard`)

2. **Load all listings** - Click all "Show More" buttons at the bottom of the page until all listings are loaded

3. **Save the page** - Press `Ctrl+S` and save as "Webpage, Complete" into the `downloads/` folder. The filename doesn't matter - the app extracts the card identity from the HTML content.

4. **Import the card** - Open the web application (`http://localhost:5001`) - it will automatically detect and import files from `downloads/`

The card will now appear in your gallery and a `.json` file will be created in `cardwatcher-data/pages/` with the correct naming convention (e.g., `Pokemon_Products_Singles_Base-Set_Charizard.json`).

#### Updating Existing Cards

Once cards are set up, you can update them directly from the web interface:

1. Open the web application (`http://localhost:5001`)
2. Click the **Start Download** button in the control bar below the search
3. The browser will open minimized and automatically download all tracked pages
4. Progress is shown in real-time with a progress bar
5. Click **Stop** to cancel the download at any time

The download control bar shows:
- Current progress (completed / total pages)
- Number of skipped pages (already downloaded)
- Current page being downloaded or wait time until next download
- Final summary when complete

Alternatively, run the downloader from the command line:

```bash
python -m app.selenium_downloader
```

Features:
- Automatic session recovery if browser crashes
- Skips already-downloaded pages
- 5-10 minute random delay between downloads to avoid detection
- Automatically clicks "Show More" buttons to load all listings
- Browser runs minimized to stay out of the way

#### Manual Updates

You can also manually update cards the same way you added them:

1. Open the CardMarket listing page in your browser (tip: each card's detail page in CardWatcher has a direct link to its CardMarket page)
2. Click all "Show More" buttons to load all listings
3. Save the page as HTML (Ctrl+S) into the `downloads/` folder
4. Open the web application - it will automatically import new downloads

### Using the Web Interface

**Search View (Home Page):**
- **Download control bar** at the top to start/stop automated downloads with progress tracking
- Browse all tracked cards as a gallery
- Use the search box to filter by card name
- Sort by: Name, Price, Price Change (€), Percentage Change (%), Lowest Price
- Select time period: Last Download, 1 Week, 1 Month, 2 Months, 6 Months
- Each card shows: available price average, sold price average, and lowest price ("From: X€")
- Green badges show newly added listings, red badges show removed/sold listings

**Card Detail View:**

![Card Detail View](image-files/individual-page.jpeg)

- Click any card to see all listings
- **Download button** to update this specific card immediately (uses Selenium)
- View individual seller prices, conditions, and languages
- See price history per listing
- Color-coded rows: green = new listing, red = ended/sold, yellow = price changed
- Filter by country or language
- Delete incorrect listings manually
- Archive/unarchive cards

### Data Files

All data files are stored in the `cardwatcher-data/` sibling directory (a separate git repo):

- **`pages/*.json`**: Active card tracking data with full listing history
- **`archive/*.json`**: Archived cards (still viewable, not updated)
- **`images/*.jpg`**: Card product images
- **`changes/price_history.json`**: Unified price history containing:
  - Current averages (available and sold listings)
  - Lowest price per card
  - Last download changes (inserted/sold counts, price changes)
  - Historical data for period comparisons (1w, 1m, 2m, 6m)

### Recalculating Metrics

If you need to recalculate price metrics without re-downloading pages (e.g., after code changes):

```bash
python -m app.recalculate_metrics
```

This updates `price_history.json` with current metrics from all page files.

## Configuration

The Flask app uses filesystem-based sessions. To change the secret key, edit `cardwatcher.py`:

```python
app.config['SECRET_KEY'] = 'your_secret_key'
```

## Supported Games

CardWatcher can track cards from any game on CardMarket:
- Pokemon
- One Piece
- Yu-Gi-Oh!
- Magic: The Gathering
- And more...

The card naming convention follows CardMarket's URL structure:
`Game_Category_Subcategory_CardName.json`

## Development

### Key Classes

**Page** (`app/page.py`):
- Represents a tracked card product with all its listings
- Methods: `import_page()`, `update_page()`, `save()`, `build_table()`

**Listing** (`app/listing.py`):
- Represents a single listing from a seller
- Tracks: price, quantity, condition, reverse holo, language, seller info, price history
- Methods: `parse_from_row()`, `build_row()`, `to_json()`, `from_json()`

**watcherbase** (`app/watcherbase.py`):
- Core processing utilities
- `import_all_pages()`: Main import loop for processing downloads
- `calculate_price_average_robust()`: Time-weighted price averaging

### Adding New Features

1. Add fields to the Listing class in `app/listing.py`
2. Parse the field in `parse_from_row()` from BeautifulSoup HTML
3. Add to JSON serialization in `to_json()` and `from_json()`
4. Update matching logic in `page.py:update_page()` if needed
5. Add to HTML rendering in `build_row()`

## Troubleshooting

**Selenium downloader fails with "invalid session id":**
- The browser may have been closed. The downloader will automatically restart.
- Check that Chrome is installed and up-to-date.

**Cloudflare challenge detected:**
- Wait for the challenge to resolve manually, or
- Try again later with longer delays between downloads

**No listings showing:**
- Ensure the "Show More" buttons were clicked before saving
- Check that the HTML was saved in the correct format

## License

This project is for personal use. CardMarket's terms of service may apply to automated access.
