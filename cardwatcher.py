from flask import Flask, render_template, request, redirect
from flask_session import Session
from language_libraries import *
from watcherbase import watcherbase
import watchersearch
import autogui

# TODO:
#  Important:
#   - Button to stop "update all"
#  Generell:
#   - Graphen überarbeiten
#       - Buttons für Zeitraum: Month, 6 Months, All Time
#   - Extra update button for Page
#   - (Make the quantity change also permanently visible) 
#   - include quantity changes in the price graph
#   - Show date when hovering over price change
#   - multithread the import function
#       - make import run in the background
#       - lock for changes file
#   - keep deleted listings around to not import them again?

app = Flask(__name__, static_folder='static')
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['SESSION_TYPE'] = 'filesystem'
Session(app)

@app.route('/', methods=['GET','POST'])
def cardwatcher():
    # methods for search site
    if request.args.get('update','') == "true":
        autogui.update_all_pages_old()
        return redirect('/')
        #watcherbase.import_all_pages()
        #search = watchersearch.build_search()
        #return render_template('search.htm',search_elements=search)
    if request.args.get('searchString',''):
        print("cardwatcher | search: " +request.args.get('searchString',''))
        page = watcherbase.import_all_pages()
        search = watchersearch.build_search(request.args.get('searchString',''))
        return render_template('search.htm',search_elements=search)

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
            language_selection = page.build_language_selection())
    # otherwise the user has not specified a page and there was no new download, so we go back to the search
    else:
        search = watchersearch.build_search()
        return render_template('search.htm',search_elements=search)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)


