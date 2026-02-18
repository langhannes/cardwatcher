import argparse
import logging
import os
import webbrowser
import threading

# Parse args and initialize data directory BEFORE importing app modules
# This ensures all modules get the correct paths
def _early_init():
    parser = argparse.ArgumentParser(description='CardWatcher Flask Application')
    parser.add_argument('-p', '--port', type=int, default=5000, help='Port to run the server on (default: 5000)')
    parser.add_argument('--no-browser', action='store_true', help='Do not open browser automatically')
    args = parser.parse_args()

    # Initialize data directory (prompts user on first run)
    from app.config import initialize_data_dir, update_paths
    data_dir = initialize_data_dir()
    update_paths(data_dir)

    return args

# Only run early init when this is the main script
_startup_args = None
if __name__ == '__main__':
    _startup_args = _early_init()

# Now import app modules - they will get the correct paths
from flask import Flask, render_template, request, redirect, jsonify, send_from_directory
from flask_session import Session
from app.language_libraries import *
from app.watcherbase import watcherbase
import app.watchersearch as watchersearch
from app.download_manager import download_manager
from app.collection import Collection, calculate_collection_price, calculate_collection_value
from app.sync import sync_manager
from app.config import PAGES_DIR, ARCHIVE_DIR, IMAGES_DIR, CHANGES_DIR, DOWNLOADS_DIR

# Filter out noisy status endpoint from logs
class StatusFilter(logging.Filter):
    def filter(self, record):
        return '/api/download/status' not in record.getMessage()

app = Flask(__name__, static_folder='static')
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['SESSION_TYPE'] = 'filesystem'
Session(app)

# Apply filter to suppress status endpoint logging
logging.getLogger('werkzeug').addFilter(StatusFilter())

@app.route('/', methods=['GET','POST'])
def cardwatcher():
    # methods for search site
    if request.args.get('searchString',''):
        print("cardwatcher | search: " +request.args.get('searchString',''))
        page = watcherbase.import_all_pages()
        sort_by = request.args.get('sortBy', 'name')
        # Smart default: descending for price fields, ascending for name
        default_order = 'asc' if sort_by == 'name' else 'desc'
        sort_order = request.args.get('order', default_order)
        price_period = request.args.get('pricePeriod', 'last')
        price_type = request.args.get('priceType', 'available')
        collection_filter = request.args.get('collection', '') == 'true'
        collection = Collection().load() if collection_filter else None
        search = watchersearch.build_search(request.args.get('searchString',''), sort_by, sort_order, price_period, price_type, collection)
        return render_template('search.htm',search_elements=search, sort_order=sort_order)

    # otherwise we're leaving the search site
    # first, check if the user requested a specifig page
    page_name = request.args.get('name','')
    print("cardwatcher | open page " + page_name)
    #download_page(page_name)
    # then check if a new page was downloaded and load that page
    # if the user specified a page, return that page instead
    
    
    page = watcherbase.import_all_pages()
    # if we have a page in memory, load the specific site
    if page_name != "":
        # Handle archive/unarchive action
        if request.args.get('archive','') == 'toggle':
            print("cardwatcher | toggling archive status for: " + page_name)
            watcherbase.toggle_archive(page_name)
            return redirect(f'/?name={page_name}')

        page = watcherbase.get_page(page_name)
        if request.args.get('delete',''):
            print("cardwatcher | delete: " +request.args.get('delete',''))
            page.delete_listings([int(request.args.get('delete',''))])

        # Get collection items for this page
        canonical_name = page_name[:-5] if page_name.endswith('.json') else page_name
        collection = Collection().load()
        collection_items = collection.get_items_for_page(canonical_name)

        # Load price history data for this page
        price_info = {
            'available_avg': 0, 'available_change': 0,
            'sold_avg': 0, 'sold_change': 0,
            'lowest_price': 0
        }
        price_history_path = os.path.join(CHANGES_DIR, "price_history.json")
        if os.path.exists(price_history_path):
            try:
                import json
                with open(price_history_path, "r", encoding="utf-8") as f:
                    price_history = json.load(f)
                if canonical_name in price_history:
                    hist = price_history[canonical_name]
                    last = hist.get('last_download', {})
                    price_info['available_avg'] = round(last.get('avg', 0) or 0, 2)
                    price_info['available_change'] = round(last.get('avg_change', 0) or 0, 2)
                    price_info['sold_avg'] = round(last.get('ended_avg', 0) or 0, 2)
                    price_info['sold_change'] = round(last.get('ended_avg_change', 0) or 0, 2)
                    price_info['lowest_price'] = round(hist.get('current_min', 0) or 0, 2)
            except (json.JSONDecodeError, IOError):
                pass

        return render_template(
            'blanko.htm',
            table_content=page.build_table(),
            main_image = page.image,
            card_name=page.card,
            set_name = page.set,
            available = page.available,
            cardmarket_link="https://www.cardmarket.com/en/"+page.canonical_name.replace('_','/'),
            country_selection = page.build_country_selection(),
            language_selection = page.build_language_selection(),
            available_languages = page.languages,
            is_archived=page.isArchived,
            page_name=page_name,
            canonical_name=canonical_name,
            collection_items=collection_items,
            in_collection=len(collection_items) > 0,
            price_info=price_info)
    # otherwise the user has not specified a page and there was no new download, so we go back to the search
    else:
        sort_by = request.args.get('sortBy', 'name')
        # Smart default: descending for price fields, ascending for name
        default_order = 'asc' if sort_by == 'name' else 'desc'
        sort_order = request.args.get('order', default_order)
        price_period = request.args.get('pricePeriod', 'last')
        price_type = request.args.get('priceType', 'available')
        collection_filter = request.args.get('collection', '') == 'true'
        collection = Collection().load() if collection_filter else None
        search = watchersearch.build_search("", sort_by, sort_order, price_period, price_type, collection)
        return render_template('search.htm',search_elements=search, sort_order=sort_order)

@app.route('/api/download/start', methods=['POST'])
def start_download():
    result = download_manager.start()
    return jsonify(result)


@app.route('/api/download/stop', methods=['POST'])
def stop_download():
    result = download_manager.stop()
    return jsonify(result)


@app.route('/api/download/status', methods=['GET'])
def download_status():
    status = download_manager.get_status()
    return jsonify(status)


@app.route('/api/download/single', methods=['POST'])
def download_single():
    """Download a single page by name."""
    data = request.get_json()
    if not data or 'page_name' not in data:
        return jsonify({"success": False, "message": "Missing page_name parameter"})

    page_name = data['page_name']
    # Remove .json extension if present
    if page_name.endswith('.json'):
        page_name = page_name[:-5]

    result = download_manager.download_single_page(page_name)
    return jsonify(result)


@app.route('/data/images/<path:filename>')
def serve_image(filename):
    return send_from_directory(IMAGES_DIR, filename)


# Collection API routes
@app.route('/api/collection', methods=['GET'])
def get_collection():
    """Get full collection with calculated prices."""
    collection = Collection().load()
    total_value, item_count, items_with_prices = calculate_collection_value(collection)

    items_data = []
    for item, price in items_with_prices:
        item_dict = item.to_dict()
        item_dict['calculated_price'] = round(price, 2)
        item_dict['total_value'] = round(price * item.quantity, 2)
        items_data.append(item_dict)

    return jsonify({
        "items": items_data,
        "total_value": round(total_value, 2),
        "item_count": item_count,
        "updated_at": collection.updated_at
    })


@app.route('/api/collection/add', methods=['POST'])
def add_to_collection():
    """Add item to collection."""
    data = request.get_json()
    if not data or 'canonical_name' not in data:
        return jsonify({"success": False, "message": "Missing canonical_name"})

    collection = Collection().load()
    item = collection.add_item(
        canonical_name=data['canonical_name'],
        condition=data.get('condition', 'NM'),
        language=data.get('language', 'English'),
        first_ed=data.get('first_ed', 0),
        reverse_holo=data.get('reverse_holo', 0),
        quantity=data.get('quantity', 1)
    )

    # Calculate price for the added item
    page = watcherbase.get_page(data['canonical_name'] + '.json')
    price = 0
    if page:
        price = calculate_collection_price(
            page, item.condition, item.language, item.first_ed, item.reverse_holo
        )

    return jsonify({
        "success": True,
        "item": item.to_dict(),
        "calculated_price": round(price, 2)
    })


@app.route('/api/collection/update', methods=['POST'])
def update_collection_item():
    """Update item quantity in collection."""
    data = request.get_json()
    if not data or 'canonical_name' not in data:
        return jsonify({"success": False, "message": "Missing canonical_name"})

    collection = Collection().load()
    success = collection.update_item(
        canonical_name=data['canonical_name'],
        condition=data.get('condition', 'NM'),
        language=data.get('language', 'English'),
        first_ed=data.get('first_ed', 0),
        reverse_holo=data.get('reverse_holo', 0),
        quantity=data.get('quantity', 1)
    )

    return jsonify({"success": success})


@app.route('/api/collection/remove', methods=['POST'])
def remove_from_collection():
    """Remove item from collection."""
    data = request.get_json()
    if not data or 'canonical_name' not in data:
        return jsonify({"success": False, "message": "Missing canonical_name"})

    collection = Collection().load()
    removed = collection.remove_item(
        canonical_name=data['canonical_name'],
        condition=data.get('condition'),
        language=data.get('language'),
        first_ed=data.get('first_ed'),
        reverse_holo=data.get('reverse_holo')
    )

    return jsonify({
        "success": len(removed) > 0,
        "removed_count": len(removed)
    })


@app.route('/api/collection/value', methods=['GET'])
def get_collection_value():
    """Get total collection value."""
    collection = Collection().load()
    total_value, item_count, _ = calculate_collection_value(collection)

    return jsonify({
        "total_value": round(total_value, 2),
        "item_count": item_count,
        "card_count": len(collection.get_canonical_names())
    })


@app.route('/api/collection/for-page/<path:canonical_name>', methods=['GET'])
def get_collection_for_page(canonical_name):
    """Get collection items for a specific page."""
    # Remove .json extension if present
    if canonical_name.endswith('.json'):
        canonical_name = canonical_name[:-5]

    collection = Collection().load()
    items = collection.get_items_for_page(canonical_name)

    # Calculate prices for each item
    page = watcherbase.get_page(canonical_name + '.json')
    items_data = []
    for item in items:
        item_dict = item.to_dict()
        price = 0
        if page:
            price = calculate_collection_price(
                page, item.condition, item.language, item.first_ed, item.reverse_holo
            )
        item_dict['calculated_price'] = round(price, 2)
        item_dict['total_value'] = round(price * item.quantity, 2)
        items_data.append(item_dict)

    return jsonify({
        "items": items_data,
        "in_collection": len(items) > 0
    })


# Sync API routes
@app.route('/api/sync/status', methods=['GET'])
def sync_status():
    """Get sync availability and last sync info."""
    info = sync_manager.check_sync_available()
    last_sync = sync_manager.get_last_sync_info()
    return jsonify({**info, **last_sync})


@app.route('/api/sync/pull', methods=['POST'])
def sync_pull():
    """Pull latest data from remote (no push)."""
    result = sync_manager.pull_only()
    return jsonify(result)


@app.route('/api/sync/full', methods=['POST'])
def sync_full():
    """Full sync: pull and push changes."""
    result = sync_manager.full_sync()
    return jsonify(result)


def is_port_available(port):
    """Check if a port is available for binding."""
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(('0.0.0.0', port))
            return True
        except OSError:
            return False


def find_available_port(start_port, max_attempts=10):
    """Find an available port starting from start_port."""
    for offset in range(max_attempts):
        port = start_port + offset
        if is_port_available(port):
            return port
    return None


if __name__ == '__main__':
    # Args were parsed and paths initialized in _early_init() above
    args = _startup_args

    # Ensure data directories exist
    for d in [PAGES_DIR, ARCHIVE_DIR, IMAGES_DIR, CHANGES_DIR, DOWNLOADS_DIR]:
        os.makedirs(d, exist_ok=True)

    # Find an available port
    port = args.port
    if not is_port_available(port):
        print(f"Port {port} is in use, looking for an available port...")
        port = find_available_port(port + 1)
        if port is None:
            print(f"Could not find an available port. Please close other applications or specify a different port with -p.")
            exit(1)
        print(f"Using port {port}")

    # Open browser automatically after short delay
    if not args.no_browser:
        url = f'http://localhost:{port}'
        threading.Timer(1.5, lambda: webbrowser.open(url)).start()

    app.run(host='0.0.0.0', port=port)


