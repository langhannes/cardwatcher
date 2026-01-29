from flask import Flask, render_template, request, redirect, jsonify
from flask_session import Session
from app.language_libraries import *
from app.watcherbase import watcherbase
import app.watchersearch as watchersearch
from app.download_manager import download_manager
import logging

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
        search = watchersearch.build_search(request.args.get('searchString',''), sort_by, sort_order, price_period)
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
            is_archived=page.isArchived,
            page_name=page_name)
    # otherwise the user has not specified a page and there was no new download, so we go back to the search
    else:
        sort_by = request.args.get('sortBy', 'name')
        # Smart default: descending for price fields, ascending for name
        default_order = 'asc' if sort_by == 'name' else 'desc'
        sort_order = request.args.get('order', default_order)
        price_period = request.args.get('pricePeriod', 'last')
        search = watchersearch.build_search("", sort_by, sort_order, price_period)
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


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001)


