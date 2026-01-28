
from bs4 import BeautifulSoup
import os
import shutil
import json
import time
from page import Page
from listing import Listing
from language_libraries import *

class watcherbase():
    
    def get_name_from_address(address):
        return address[30:].replace('/','_')

    def get_address_from_name(name):
        return "https://www.cardmarket.com/en/" + name[:-5].replace('_','/')

    def delete_download(file_name):
        print("delete_download | deleting html " + file_name)
        os.remove(os.path.join("downloads",file_name))
        print("delete_download | deleting folder " + file_name[:-4] + "-Dateien")
        try:
            shutil.rmtree(os.path.join("downloads",file_name[:-4]+"-Dateien"))
        except:
            print("delete_download | no folder to delete")

    def calculate_price_average_simple(prices):
        """
        Calculate simple price average without outlier filtering.
        Use this for ended/sold listings where we want to track actual sale prices.

        Args:
            prices: List of prices (floats)

        Returns:
            float: Simple average price
        """
        if not prices:
            return 0.0
        return sum(prices) / len(prices)

    def calculate_price_average_time_weighted(price_date_pairs, half_life_days=30, reference_time=None):
        """
        Calculate time-weighted price average where recent sales have more influence.
        Uses exponential decay: weight = 2^(-days_ago / half_life)

        With half_life=30 days:
        - Today's sale: weight 1.0
        - 30 days ago: weight 0.5
        - 60 days ago: weight 0.25
        - 90 days ago: weight 0.125

        Args:
            price_date_pairs: List of (price, timestamp) tuples
            half_life_days: Days until weight is halved (default 30)
            reference_time: Reference timestamp for "now" (default: current time)
                           Use this to calculate historical weighted averages

        Returns:
            float: Time-weighted average price
        """
        import math

        if not price_date_pairs:
            return 0.0

        now = reference_time if reference_time is not None else time.time()
        total_weight = 0.0
        weighted_sum = 0.0

        for price, timestamp in price_date_pairs:
            try:
                ts = float(timestamp) if timestamp else 0
            except (ValueError, TypeError):
                ts = 0

            if ts <= 0:
                # If no valid timestamp, use minimal weight
                days_ago = 365  # Assume old
            else:
                days_ago = (now - ts) / (24 * 60 * 60)
                # Only include if the sale happened before the reference time
                if days_ago < 0:
                    continue  # Skip future sales relative to reference time

            # Exponential decay weight
            weight = math.pow(2, -days_ago / half_life_days)

            weighted_sum += price * weight
            total_weight += weight

        if total_weight == 0:
            return 0.0

        return weighted_sum / total_weight

    def calculate_price_average_robust(prices):
        """
        Calculate price average with IQR-based outlier filtering.
        Falls back to simple mean for small datasets.

        Uses the Interquartile Range (IQR) method to detect and filter outliers:
        - Q1 = 25th percentile
        - Q3 = 75th percentile
        - IQR = Q3 - Q1
        - Lower bound = Q1 - 1.5 * IQR
        - Upper bound = Q3 + 1.5 * IQR
        - Values outside these bounds are considered outliers and excluded

        Args:
            prices: List of prices (floats)

        Returns:
            float: Filtered average price
        """
        if not prices:
            return 0.0

        if len(prices) < 4:
            # Too few data points for IQR, use simple mean
            return sum(prices) / len(prices)

        # Sort prices for quartile calculation
        sorted_prices = sorted(prices)
        n = len(sorted_prices)

        # Calculate quartiles (using simple method)
        q1_idx = n // 4
        q3_idx = 3 * n // 4
        q1 = sorted_prices[q1_idx]
        q3 = sorted_prices[q3_idx]

        # Calculate IQR and bounds
        iqr = q3 - q1

        # If IQR is 0 (all prices very similar), no filtering needed
        if iqr == 0:
            return sum(prices) / len(prices)

        lower_bound = q1 - 1.5 * iqr
        upper_bound = q3 + 1.5 * iqr

        # Filter outliers
        filtered_prices = [p for p in prices if lower_bound <= p <= upper_bound]

        # Ensure we don't filter out everything
        if not filtered_prices:
            # All were outliers? Use original data
            return sum(prices) / len(prices)

        return sum(filtered_prices) / len(filtered_prices)

    def get_price_at_time(listing, target_time):
        """
        Get the price that was active for a listing at a specific point in time.
        Uses the previous_prices history to determine what price was active then.

        Args:
            listing: Listing object with price and previous_prices
            target_time: Unix timestamp of the historical point

        Returns:
            float: The price that was active at target_time
        """
        # Start with current price as candidate
        candidate_price = listing.price

        # If no previous prices, return current price
        if not listing.previous_prices:
            return candidate_price

        # Go through previous_prices in reverse order (most recent first)
        # Each entry is [old_price, change_date] - the old_price was replaced at change_date
        for prev_entry in reversed(listing.previous_prices):
            try:
                old_price = float(prev_entry[0])
                change_date_str = prev_entry[1] if len(prev_entry) > 1 else ''

                # Skip entries with no date (user requested to ignore these)
                if not change_date_str:
                    continue

                change_date = float(change_date_str)

                # If the price change happened AFTER target_time, the current candidate
                # wasn't active yet at target_time - use the old_price instead
                if change_date > target_time:
                    candidate_price = old_price
                else:
                    # This change happened before target_time, so we've found our answer
                    break
            except (ValueError, TypeError, IndexError):
                # Skip malformed entries
                continue

        return candidate_price

    def calculate_historical_average(page, days_ago):
        """
        Calculate what the average price would have been X days ago.
        Includes listings that were available at that time:
        - first_date <= cutoff (existed by then)
        - AND either still active now, or ended after the cutoff date

        Args:
            page: Page object with listings
            days_ago: Number of days to look back

        Returns:
            float or None: Historical average price, or None if insufficient data
        """
        cutoff = time.time() - (days_ago * 24 * 60 * 60)

        historical_prices = []
        for listing in page.listings:
            try:
                first_date = float(listing.first_date) if listing.first_date else 0
            except (ValueError, TypeError):
                first_date = 0

            # Listing must have existed at the cutoff time
            if first_date <= 0 or first_date > cutoff:
                continue

            # Check if listing was still active at cutoff time
            if listing.ended:
                # For ended listings, check if they ended after the cutoff
                # The 'date' field holds the last seen date before ending
                try:
                    last_seen = float(listing.date) if listing.date else 0
                except (ValueError, TypeError):
                    last_seen = 0
                # If last seen before cutoff, it wasn't available at cutoff
                if last_seen < cutoff:
                    continue

            # Listing was available at the historical point in time
            # Use the price that was active at the cutoff time, not current price
            historical_price = watcherbase.get_price_at_time(listing, cutoff)
            historical_prices.append(historical_price)

        if historical_prices:
            return watcherbase.calculate_price_average_robust(historical_prices)
        return None

    def calculate_historical_ended_average(page, days_ago):
        """
        Calculate what the time-weighted average price of ended listings would have been X days ago.
        Only includes listings that were already ended by that time, weighted by recency
        relative to that historical point.

        Args:
            page: Page object with listings
            days_ago: Number of days to look back

        Returns:
            float or None: Historical ended average price, or None if insufficient data
        """
        cutoff = time.time() - (days_ago * 24 * 60 * 60)

        historical_ended_pairs = []
        for listing in page.listings:
            # Only consider currently ended listings
            if not listing.ended:
                continue

            # Check if the listing was already ended at the cutoff time
            # The 'date' field holds the last seen date (when it ended)
            try:
                last_seen = float(listing.date) if listing.date else 0
            except (ValueError, TypeError):
                last_seen = 0

            # If the listing ended before or at the cutoff, it was ended at that time
            if last_seen > 0 and last_seen <= cutoff:
                historical_ended_pairs.append((listing.price, listing.date))

        if historical_ended_pairs:
            # Calculate time-weighted average relative to the cutoff point
            return watcherbase.calculate_price_average_time_weighted(
                historical_ended_pairs, reference_time=cutoff
            )
        return None

    def calculate_historical_available_count(page, days_ago):
        """
        Calculate how many listings were available X days ago.
        A listing was available if:
        - first_date <= cutoff (existed by then)
        - AND either not ended now, or ended after the cutoff date

        Args:
            page: Page object with listings
            days_ago: Number of days to look back

        Returns:
            int: Number of listings that were available at that time
        """
        cutoff = time.time() - (days_ago * 24 * 60 * 60)
        count = 0

        for listing in page.listings:
            try:
                first_date = float(listing.first_date) if listing.first_date else 0
            except (ValueError, TypeError):
                first_date = 0

            # Listing must have existed at the cutoff time
            if first_date <= 0 or first_date > cutoff:
                continue

            # Check if listing was still active at cutoff time
            if listing.ended:
                # For ended listings, check if they ended after the cutoff
                try:
                    last_seen = float(listing.date) if listing.date else 0
                except (ValueError, TypeError):
                    last_seen = 0
                # If last seen before cutoff, it wasn't available at cutoff
                if last_seen < cutoff:
                    continue

            # Listing was available at the historical point in time
            count += 1

        return count

    def calculate_availability_changes(page, days_ago):
        """
        Calculate how many listings were added and removed within the last X days.

        Added: Listings that are currently available and were first seen within the period
        Removed: Listings that ended within the period (regardless of when first seen)

        Args:
            page: Page object with listings
            days_ago: Number of days to look back

        Returns:
            tuple: (added_count, removed_count)
        """
        cutoff = time.time() - (days_ago * 24 * 60 * 60)
        added = 0
        removed = 0

        for listing in page.listings:
            try:
                first_date = float(listing.first_date) if listing.first_date else 0
            except (ValueError, TypeError):
                first_date = 0

            try:
                last_seen = float(listing.date) if listing.date else 0
            except (ValueError, TypeError):
                last_seen = 0

            # Check if listing is currently active (not ended)
            if not listing.ended:
                # Active listing - check if it's new since cutoff
                if first_date > cutoff:
                    added += 1
            else:
                # Ended listing - check if it ended within the period
                # (last_seen > cutoff means it ended after the cutoff, i.e., within the period)
                if last_seen > cutoff:
                    removed += 1

        return (added, removed)

    def calculate_all_period_averages(page):
        """
        Calculate historical averages for all time periods, for both
        available (active) and ended (sold) listings.

        Returns dict with format:
        {
            'current_avg': float,
            'current_ended_avg': float,
            'current_available': int,
            '1w': {
                'historical_avg': float or None,
                'change': float or None,
                'historical_ended_avg': float or None,
                'ended_change': float or None,
                'historical_available': int or None,
                'available_change': int or None
            },
            ...
        }
        """
        periods = {
            '1w': 7,
            '1m': 30,
            '2m': 60,
            '6m': 180
        }

        # Calculate current average (all active listings)
        current_prices = [l.price for l in page.listings if not l.ended]
        current_avg = watcherbase.calculate_price_average_robust(current_prices) if current_prices else 0

        # Count current available listings
        current_available = len(current_prices)

        # Calculate current ended average using time-weighted approach
        # Recent sales have more influence than older sales
        ended_price_date_pairs = []
        for l in page.listings:
            if l.ended:
                ended_price_date_pairs.append((l.price, l.date))
        current_ended_avg = watcherbase.calculate_price_average_time_weighted(ended_price_date_pairs) if ended_price_date_pairs else 0

        result = {
            'current_avg': round(current_avg, 2),
            'current_ended_avg': round(current_ended_avg, 2),
            'current_available': current_available
        }

        for period_name, days in periods.items():
            period_data = {}

            # Available listings - price average
            historical_avg = watcherbase.calculate_historical_average(page, days)
            if historical_avg is not None and current_avg > 0:
                period_data['historical_avg'] = round(historical_avg, 2)
                period_data['change'] = round(current_avg - historical_avg, 2)
            else:
                period_data['historical_avg'] = None
                period_data['change'] = None

            # Available listings - count and detailed changes
            historical_available = watcherbase.calculate_historical_available_count(page, days)
            added, removed = watcherbase.calculate_availability_changes(page, days)
            period_data['historical_available'] = historical_available if historical_available > 0 else None
            period_data['available_change'] = current_available - historical_available if historical_available > 0 else None
            period_data['listings_added'] = added
            period_data['listings_removed'] = removed

            # Ended listings
            historical_ended_avg = watcherbase.calculate_historical_ended_average(page, days)
            if historical_ended_avg is not None and current_ended_avg > 0:
                period_data['historical_ended_avg'] = round(historical_ended_avg, 2)
                period_data['ended_change'] = round(current_ended_avg - historical_ended_avg, 2)
            else:
                period_data['historical_ended_avg'] = None
                period_data['ended_change'] = None

            result[period_name] = period_data

        return result

    def get_page(page_name):
        active_page = Page()
        active_page.canonical_name = page_name[:-5]
        active_page.import_page(os.path.join("pages",page_name))
        return active_page

    def toggle_archive(page_name):
        """
        Toggle a page between archived and active state.
        Moves the file between pages/ and archive/ folders.
        Handles .json format files.

        Args:
            page_name: Name of the .json file

        Returns:
            bool: True if archived, False if unarchived
        """
        pages_path = os.path.join("pages", page_name)
        archive_path = os.path.join("archive", page_name)

        # Check if file is currently in pages/ (active)
        if os.path.exists(pages_path):
            # Move to archive
            shutil.move(pages_path, archive_path)
            print(f"toggle_archive | Archived: {page_name}")
            return True
        # Check if file is in archive/
        elif os.path.exists(archive_path):
            # Move to active pages
            shutil.move(archive_path, pages_path)
            print(f"toggle_archive | Unarchived: {page_name}")
            return False
        else:
            print(f"toggle_archive | ERROR: File not found in pages/ or archive/: {page_name}")
            return None
    
    def save_image(path,new_path):
        try: 
            if os.path.exists(new_path):
                return
            shutil.copy2(path, new_path)
        except Exception as e:
            print("save_image: ERROR: " + str(e))

    def import_all_pages():
        changes = {}
        price_changes = {}
        price_history = {}
        file_list = os.listdir("downloads")
        file_info_list = [(file_name, os.path.getmtime(os.path.join("downloads",file_name))) for file_name in file_list if file_name.lower().endswith(".htm")]
        sorted_file_info_list = sorted(file_info_list, key=lambda x: x[1])
        for file_name,timestamp in sorted_file_info_list:
            print("import_all_pages | importing " + file_name)
            content = ""
            with open(os.path.join("downloads",file_name),'r',encoding="utf-8") as f:
                content = f.read()

            parsed_html = BeautifulSoup(content)
            if not parsed_html.body:
                watcherbase.delete_download(file_name)
                print("import_all_pages | no html found")
                continue
            table_body = parsed_html.body.find('div', attrs={'class':'table-body'})

            page = Page()
            if not parsed_html.find_all('link'):
                watcherbase.delete_download(file_name)
                print("import_all_pages | no link found")
                continue
            page.canonical_name = watcherbase.get_name_from_address(parsed_html.find_all('link')[0]['href'])

            if not parsed_html.body.find('div',attrs={'class':'page-title-container'}):
                watcherbase.delete_download(file_name)
                print("import_all_pages | no page-title found")
                continue
            page.card = parsed_html.body.find('div',attrs={'class':'page-title-container'}).find('h1').find(string=True,recursive=False).replace('Ã©','e')
            
            if not parsed_html.body.find('div',attrs={'id':'articleFilterSellerLocation'}):
                watcherbase.delete_download(file_name)
                print("import_all_pages | no seller location filter found")
                continue
            checkmark = parsed_html.body.find('div',attrs={'id':'articleFilterSellerLocation'}).find('input',attrs={'class':'form-check-input'})
            checked_country = parsed_html.body.find('div',attrs={'id':'articleFilterSellerLocation'}).find('div',attrs={'class','form-check'}).find('label').text
            page.only_germany = False
            if 'checked' in checkmark.attrs and ("Deutschland" in checked_country or "Germany" in checked_country):
                page.only_germany = (checkmark['checked'] == 'checked')
            print("import_all_pages | only listings from germany: " + str(page.only_germany))

            # get the active languages
            all_languages = []
            product_languages = parsed_html.body.find('div',attrs={'id':'articleFilterProductLanguage'})
            if not product_languages:
                watcherbase.delete_download(file_name)
                print("import_all_pages | no language filter found")
                continue
            for language in product_languages.find_all('div',attrs={'class':'form-check'}):
                all_languages.append(language_to_english[language.text] if language.text in language_to_english else language.text)
                checkbox = language.find('input',attrs={'class':'form-check-input'})
                if "checked" in checkbox.attrs and checkbox['checked'] == "checked":
                    page.languages.append(language.text)
            # if no language is checked, all languages in the list are active
            if len(page.languages) == 0:
                for language in all_languages:
                    page.languages.append(language_to_english[language] if language in language_to_english else language)

            # get the product image
            card_slideshow = parsed_html.body.find('div',attrs={'class':'card-slideshow'})
            if card_slideshow:
                image_path = card_slideshow.find_all('div',attrs={'class':'slide'})[1].find('img')['src'].replace('%20',' ').replace('%C3%A9','é')
            else:
                image_path = parsed_html.body.find('section',attrs={'id':'image'}).find('img')['src'].replace('%20',' ').replace('%C3%A9','é')
            page.image = "static/Blanko/images/" + (page.canonical_name) + ".jpg" 
            watcherbase.save_image(os.path.join("downloads",image_path),page.image)
            print("import_all_pages | image saved under " + page.image)
            
            # get the set the product is from    
            page.set = parsed_html.body.find('div',attrs={'class':'page-title-container'}).find('h1').find('span').text.replace('Ã©','e')
            
            # check if the user loaded all listings
            if parsed_html.find('button',attrs={'id':'loadMoreButton'}):
                page.loadMoreButton = True
            
            for item in parsed_html.find_all('button', attrs={'class':'mt-2 text-muted text-center'}):
                if item.text == "We only show the first 300 articles. Please use the filters for more precise results.":
                    page.loadMoreButton = True
                    break

            # iterate over the available listings and parse them
            prices = []
            for row in table_body.find_all('div', attrs={'class':'article-row'}):
                # skip rows that sell playsets, those are usually not actual playsets, but some other random combinations
                if row.find('span',attrs={'data-bs-original-title':'Playset'}):
                    continue
                # skip additional rows by active seller
                if "stockRow" in row["id"] or "shoppingCartRow" in row["id"]:
                    continue
                listing = Listing()
                listing.card = page.card
                listing.parse_from_row(row)
                listing.date = timestamp
                listing.canonical_name = page.canonical_name
                page.listings.append(listing)
                prices.append(listing.price)
            page.price_average = watcherbase.calculate_price_average_robust(prices)

            # open the corresponding old page and compare it with the newly created one
            old_page = Page()
            old_page.canonical_name = page.canonical_name
            old_page.import_page(old_page.canonical_name+".json")
            old_page.update_page(page)
            old_page.save()
            print("import_all_pages | page saved under " + os.path.join("pages",(old_page.canonical_name+".json")))
            watcherbase.delete_download(file_name)
            print(old_page.inserted)
            print(old_page.sold)
            changes[page.canonical_name] = str(old_page.inserted) + "/" + str(old_page.sold)
            price_changes[page.canonical_name] = str(old_page.price_average) + "/" + str(old_page.price_change)
            # Calculate period-based price averages
            price_history[page.canonical_name] = watcherbase.calculate_all_period_averages(old_page)
        # print changes to files
        with open("changes.txt", "r") as f:
            old_changes = {}
            for line in f.read().split('\n'):
                if len(line.split(" ")) < 2:
                    continue
                old_changes[line.split(" ")[0]] = line.split(" ")[1]
            for key, value in changes.items():
                old_changes[key] = value
        f.close()
        with open("changes.txt", "w") as f:
            for key,value in old_changes.items():
                f.write(key + " " + str(value) + "\n")
        f.close()

        with open("price_changes.txt", "r") as f:
            old_changes = {}
            for line in f.read().split('\n'):
                if len(line.split(" ")) < 2:
                    continue
                old_changes[line.split(" ")[0]] = line.split(" ")[1]
            for key, value in price_changes.items():
                old_changes[key] = value
        f.close()
        with open("price_changes.txt", "w") as f:
            for key,value in old_changes.items():
                f.write(key + " " + str(value) + "\n")
        f.close()

        # Load existing price_history.json, merge with new data, and save
        existing_price_history = {}
        if os.path.exists("price_history.json"):
            try:
                with open("price_history.json", "r", encoding="utf-8") as f:
                    existing_price_history = json.load(f)
            except (json.JSONDecodeError, IOError):
                existing_price_history = {}

        # Merge new price history data
        for key, value in price_history.items():
            existing_price_history[key] = value

        # Save updated price history
        with open("price_history.json", "w", encoding="utf-8") as f:
            json.dump(existing_price_history, f, indent=2)
