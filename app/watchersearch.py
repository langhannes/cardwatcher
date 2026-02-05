from datetime import datetime
import os
import json

def build_search(search_term="", sort_by="name", sort_order="asc", price_period="last"):
    """
    Build the search view HTML.

    Args:
        search_term: Filter pages by name
        sort_by: Sort field (name, price, priceChange, percentChange)
        sort_order: Sort direction (asc, desc)
        price_period: Price comparison period (last, 1w, 1m, 2m, 6m)
    """
    changes = {}
    with open("changes/changes.txt","r") as f:
        for line in f.readlines():
            line = line.strip()
            if line == "":
                continue
            changes[line.split(" ")[0]] = line.split(" ")[1]
    f.close()
    price_changes = {}
    with open("changes/price_changes.txt","r") as f:
        for line in f.readlines():
            line = line.strip()
            if line == "":
                continue
            price_changes[line.split(" ")[0]] = line.split(" ")[1]
    f.close()

    # Load price history for period-based comparisons
    price_history = {}
    if os.path.exists("changes/price_history.json"):
        try:
            with open("changes/price_history.json", "r", encoding="utf-8") as f:
                price_history = json.load(f)
        except (json.JSONDecodeError, IOError):
            price_history = {}

    # Build data structure with all sort-relevant information
    file_list = [f for f in os.listdir("pages") if f.endswith('.json')]
    file_data_list = []

    search_terms = search_term.lower().split() if search_term else []
    for file_name in file_list:
        # if there is a search term, all words in the term have to be in the canonical name
        if search_term and any([term not in file_name.lower() for term in search_terms]):
            continue
            
        canonical_name = file_name[:-5]
        timestamp = os.path.getmtime(os.path.join("pages", file_name))

        # Extract price data for sorting based on selected period
        price_avg = 0.0
        price_chg = 0.0
        percent_chg = 0.0

        if price_period == "last":
            # Use last download comparison
            if canonical_name in price_changes:
                parts = price_changes[canonical_name].split('/')
                price_avg = float(parts[0])
                price_chg = float(parts[1])
                if price_avg > 0:
                    percent_chg = (price_chg / price_avg) * 100
        else:
            # Use period-based comparison
            if canonical_name in price_history:
                hist = price_history[canonical_name]
                price_avg = hist.get('current_avg', 0) or 0
                period_data = hist.get(price_period, {})
                if period_data and period_data.get('change') is not None:
                    price_chg = period_data['change']
                if price_avg > 0:
                    percent_chg = (price_chg / price_avg) * 100

        file_data_list.append({
            'file_name': file_name,
            'canonical_name': canonical_name,
            'timestamp': timestamp,
            'price_avg': price_avg,
            'price_chg': price_chg,
            'percent_chg': percent_chg
        })

    # Apply sorting based on parameters
    if sort_by == "price":
        file_data_list.sort(key=lambda x: x['price_avg'], reverse=(sort_order == "desc"))
    elif sort_by == "priceChange":
        file_data_list.sort(key=lambda x: x['price_chg'], reverse=(sort_order == "desc"))
    elif sort_by == "percentChange":
        file_data_list.sort(key=lambda x: x['percent_chg'], reverse=(sort_order == "desc"))
    else:  # default to name
        file_data_list.sort(key=lambda x: x['file_name'], reverse=(sort_order == "desc"))

    # Generate HTML from sorted data
    search = ""
    for data in file_data_list:
        file_name = data['file_name']
        canonical_name = data['canonical_name']
        timestamp = data['timestamp']
        # Get canonical name (strip .json extension) for lookup
        canonical_name = file_name[:-5]

        # Build availability change badges based on selected period
        availability_badges = ""
        badge_parts = []

        if price_period == "last":
            # Use last download comparison (changes.txt)
            if canonical_name in changes:
                inserted = int(changes[canonical_name].split('/')[0])
                sold = int(changes[canonical_name].split('/')[1])
                if inserted > 0:
                    badge_parts.append(f'<span style="color: rgb(34,139,34); font-weight: bold;">+{inserted}</span>')
                if sold > 0:
                    badge_parts.append(f'<span style="color: rgb(220, 20, 60); font-weight: bold;">-{sold}</span>')
        else:
            # Use period-based comparison from price_history
            if canonical_name in price_history:
                hist = price_history[canonical_name]
                period_data = hist.get(price_period, {})
                listings_added = period_data.get('listings_added', 0)
                listings_removed = period_data.get('listings_removed', 0)
                if listings_added > 0:
                    badge_parts.append(f'<span style="color: rgb(34,139,34); font-weight: bold;">+{listings_added}</span>')
                if listings_removed > 0:
                    badge_parts.append(f'<span style="color: rgb(220, 20, 60); font-weight: bold;">-{listings_removed}</span>')

        if badge_parts:
            availability_badges = '<div style="position: absolute; top: 4px; right: 4px; background: rgba(255,255,255,0.9); padding: 2px 6px; border-radius: 4px; font-size: 0.8em; display: flex; gap: 6px;">' + ' '.join(badge_parts) + '</div>'
        price_string = "--€ (0€)"
        price_arrow = ""
        price_style = "font-size: 0.85em; font-weight: bold; background: rgba(255,255,255,0.85); padding: 2px 4px; border-radius: 4px; display: inline-block;"

        # Determine price_average and price_change based on selected period
        price_average = 0.0
        price_change = 0.0
        has_price_data = False

        if price_period == "last":
            # Use last download comparison (existing behavior)
            if canonical_name in price_changes:
                parts = price_changes[canonical_name].split('/')
                price_average = float(parts[0])
                price_change = float(parts[1])
                has_price_data = True
        else:
            # Use period-based comparison from price_history
            if canonical_name in price_history:
                hist = price_history[canonical_name]
                price_average = hist.get('current_avg', 0) or 0
                period_data = hist.get(price_period, {})
                if period_data and period_data.get('change') is not None:
                    price_change = period_data['change']
                    has_price_data = True
                elif price_average > 0:
                    # We have current avg but no historical data for this period
                    price_change = 0
                    has_price_data = True

        if has_price_data and price_average > 0:
            sign = '+' if price_change >= 0 else ''
            percentage_change = (price_change / price_average) * 100

            # Add arrow indicator based on price change
            if price_change > 0:
                price_arrow = " ↑"
            elif price_change < 0:
                price_arrow = " ↓"
            else:
                price_arrow = " →"

            # Show percentage when sorting by percentage, otherwise show absolute change
            if sort_by == "percentChange":
                price_string = f"Avail: {round(price_average,2)}€ ({sign}{round(percentage_change,1)}%){price_arrow}"
            else:
                price_string = f"Avail: {round(price_average,2)}€ ({sign}{round(price_change,2)}€){price_arrow}"

            # Add color styling: green for price increase (good), red for price decrease
            if price_change > 0:
                # Price went up - green
                price_style = "font-size: 0.85em; color: rgb(34,139,34); font-weight: bold; background: rgba(255,255,255,0.85); padding: 2px 4px; border-radius: 4px; display: inline-block;"
            elif price_change < 0:
                # Price went down - red
                price_style = "font-size: 0.85em; color: rgb(220, 20, 60); font-weight: bold; background: rgba(255,255,255,0.85); padding: 2px 4px; border-radius: 4px; display: inline-block;"
            else:
                # No change - neutral with backdrop
                price_style = "font-size: 0.85em; font-weight: bold; background: rgba(255,255,255,0.85); padding: 2px 4px; border-radius: 4px; display: inline-block;"

        # Determine ended (sold) price_average and price_change based on selected period
        ended_price_string = ""
        ended_price_style = "font-size: 0.85em; font-weight: bold; background: rgba(200,200,200,0.85); padding: 2px 4px; border-radius: 4px; display: inline-block;"
        ended_price_average = 0.0
        ended_price_change = 0.0
        has_ended_price_data = False

        # Ended listings only available for period-based comparison (not "last")
        if price_period != "last" and canonical_name in price_history:
            hist = price_history[canonical_name]
            ended_price_average = hist.get('current_ended_avg', 0) or 0
            period_data = hist.get(price_period, {})
            if period_data and period_data.get('ended_change') is not None:
                ended_price_change = period_data['ended_change']
                has_ended_price_data = True
            elif ended_price_average > 0:
                ended_price_change = 0
                has_ended_price_data = True

        if has_ended_price_data and ended_price_average > 0:
            ended_sign = '+' if ended_price_change >= 0 else ''
            ended_percentage_change = (ended_price_change / ended_price_average) * 100

            if ended_price_change > 0:
                ended_arrow = " ↑"
            elif ended_price_change < 0:
                ended_arrow = " ↓"
            else:
                ended_arrow = " →"

            # Show percentage when sorting by percentage, otherwise show absolute change
            if sort_by == "percentChange":
                ended_price_string = f"Sold: {round(ended_price_average,2)}€ ({ended_sign}{round(ended_percentage_change,1)}%){ended_arrow}"
            else:
                ended_price_string = f"Sold: {round(ended_price_average,2)}€ ({ended_sign}{round(ended_price_change,2)}€){ended_arrow}"

            if ended_price_change > 0:
                ended_price_style = "font-size: 0.85em; color: rgb(34,139,34); font-weight: bold; background: rgba(200,200,200,0.85); padding: 2px 4px; border-radius: 4px; display: inline-block;"
            elif ended_price_change < 0:
                ended_price_style = "font-size: 0.85em; color: rgb(220, 20, 60); font-weight: bold; background: rgba(200,200,200,0.85); padding: 2px 4px; border-radius: 4px; display: inline-block;"

        article_name = file_name[:-5].split('_')[-1].replace('-',' ')

        # Build ended price HTML if available
        ended_price_html = ""
        if ended_price_string:
            ended_price_html = "<div style=\"" + ended_price_style + "\">" + ended_price_string + "</div>"

        search += "<div class=\"d-flex mb-4 col-12 col-sm-6 col-md-4 col-lg-2\">" + \
                    "<a name=\"" + file_name + "\" href=\"?name="+file_name+"\" class=\"card text-center w-100 galleryBox\" style=\"position: relative;\">" + \
                        availability_badges + \
                        "<img src=\"static/Blanko/images/" + file_name[:-5] +".jpg" + \
                        "\" alt=\"" + article_name + "\" class=\"lazy card-img-top img-fluid\">" + \
                        "<div class=\"card-body d-flex flex-column p-2\" style=\"gap: 2px;\">" + \
                            "<div class=\"card-title\" style=\"font-size: 0.9em; font-weight: bold; margin-bottom: 2px;\">" + \
                                article_name + \
                            "</div>" + \
                            "<div style=\"font-size: 0.75em; color: #666;\">(" + \
                                datetime.fromtimestamp(float(timestamp)).strftime('%d.%m.%Y') + \
                            ")</div>" + \
                            "<div style=\"" + price_style + "\">" + \
                               price_string + \
                            "</div>" + \
                            ended_price_html + \
                        "</div>" + \
                    "</a>" + \
                  "</div>"
    search += "<h1 class=\"page-header\">Archive</h1>"
    file_list = [f for f in os.listdir("archive") if f.endswith('.json')]
    file_info_list = [(file_name, os.path.getmtime(os.path.join("archive",file_name))) for file_name in file_list]
    sorted_file_list = sorted(file_info_list, key=lambda x: x[0])
    for file_name,timestamp in sorted_file_list:
        if search_term and search_term.lower() not in file_name.lower():
            continue
        article_name = file_name[:-5].split('_')[-1].replace('-',' ')
        search += "<div class=\"d-flex mb-4 col-12 col-sm-6 col-md-4 col-lg-2\">" + \
                    "<a name=\"" + file_name + "\" href=\"?name="+file_name+"\" class=\"card text-center w-100 galleryBox\">" + \
                        "<img src=\"static/Blanko/images/" + file_name[:-5] +".jpg" + \
                        "\" alt=\"" + article_name + "\" class=\"lazy card-img-top img-fluid\">" + \
                        "<div class=\"card-body d-flex flex-column p-2\" style=\"gap: 2px;\">" + \
                            "<div class=\"card-title\" style=\"font-size: 0.9em; font-weight: bold; margin-bottom: 2px;\">" + \
                                article_name + \
                            "</div>" + \
                            "<div style=\"font-size: 0.75em; color: #666;\">(" + \
                                datetime.fromtimestamp(float(timestamp)).strftime('%d.%m.%Y') + \
                            ")</div>" + \
                        "</div>" + \
                    "</a>" + \
                  "</div>"
    return search